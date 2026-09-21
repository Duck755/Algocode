"""Model-driven project contract discovery and compilation."""

from __future__ import annotations

import ast
import fnmatch
import json
import re
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from algocode.context.builder import SYSTEM_RULES
from algocode.project_layout import ProjectLayout
from algocode.providers.errors import ProviderError
from algocode.providers.factory import build_provider
from algocode.providers.types import Message, ModelRequest
from algocode.runtime.analysis import discover_required_files
from algocode.runtime.model_log import (
    ModelCallLogger,
    model_call_duration_ms,
    model_error_traceback,
)
from algocode.structured_output import parse_model

MAX_CONTRACT_SOURCE_BYTES = 160_000
MAX_CONTRACT_FILE_BYTES = 80_000


class PublicApiItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    symbol: str
    signature: str = ""
    behavior: str = ""


class ConfigurationItem(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    field: str
    default: str = ""
    variants: tuple[str, ...] = ()
    must_honor: bool = True


class ObservableOutputs(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    deterministic: tuple[str, ...] = ()
    volatile: tuple[str, ...] = ()


class ContractObligation(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    target: str = Field(min_length=1)
    assertion: str = Field(min_length=1)
    kind: str = Field(default="behavior", min_length=1)


class ScalingInput(BaseModel):
    """One benchmark input at a declared problem size."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    size: int = Field(gt=0)
    input: str = ""


class ProjectContract(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")

    schema_version: int = Field(default=1, ge=1)
    purpose: str
    entrypoints: tuple[str, ...] = ()
    public_api: tuple[PublicApiItem, ...] = ()
    configuration: tuple[ConfigurationItem, ...] = ()
    state_transitions: tuple[str, ...] = ()
    error_contracts: tuple[str, ...] = ()
    observable_outputs: ObservableOutputs = Field(default_factory=ObservableOutputs)
    invariants: tuple[str, ...] = ()
    performance_goal: str = ""
    must_not_change: tuple[str, ...] = ()
    protected_files: tuple[str, ...] = ()
    benchmark_scaling: tuple[ScalingInput, ...] = ()
    benchmark_harness: str = ""
    unknowns: tuple[str, ...] = ()
    test_obligations: tuple[ContractObligation, ...] = ()
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    contract_test_source: str = ""
    contract_source: str = "model"


class ContractDiscoveryService:
    """Ask one model session to derive a project-wide behavior contract."""

    def __init__(self, context) -> None:
        self._context = context

    async def discover(self, root: str | Path, *, language: str) -> ProjectContract:
        project_root = Path(root).resolve()
        snapshot = _source_snapshot(project_root)
        try:
            provider, model = build_provider(
                self._context.config,
                redactor=self._context.secret_redactor,
            )
        except ProviderError:
            return _fallback_contract(project_root, language)

        schema = json.dumps(
            ProjectContract.model_json_schema(),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        contract_test_instruction = _contract_test_instruction(language)
        benchmark_harness_instruction = _benchmark_harness_instruction(language)
        request = ModelRequest(
            request_id=f"req_{uuid4().hex}",
            model=model,
            system=SYSTEM_RULES,
            messages=(
                Message(
                    role="user",
                    content=(
                        "You are a contract auditor, not an optimizer.\n\n"
                        "Analyze the project and return exactly one JSON ProjectContract. "
                        "Infer the optimization objective from the code and documentation, not "
                        "from a fixed template.\n\n"
                        "The purpose and performanceGoal must form a concrete optimization "
                        "objective: "
                        "name the target entrypoint/APIs, the measured resource, the intended "
                        "direction, and the exact behavior/outputs that must remain unchanged. "
                        "Never "
                        "use a vague goal such as 'make it faster'.\n\n"
                        "Build a complete behavior inventory before considering performance. "
                        "For every public API, capture its signature, preconditions, side "
                        "effects, postconditions, exact return semantics, ordering and "
                        "tie-breaking "
                        "rules, state mutations, boundary cases, and errors. For every stateful "
                        "object, capture the invariant after each mutating operation, including "
                        "identity, count/length consistency, structural validity, augmented "
                        "fields, "
                        "and iterator/query consistency. For every configuration axis, capture its "
                        "default, variants, and observable semantic effect.\n\n"
                        "Do not merely describe behavior. Populate testObligations with executable "
                        "assertions. Every public API, state transition, error contract, "
                        "invariant, "
                        "ordering rule, and deterministic output must map to at least one "
                        "testObligations entry. Use target, assertion, and kind fields. An "
                        "assertion "
                        "must state the exact observable result and must fail when the behavior is "
                        "changed. Never leave an obligation as 'test broadly' or 'preserve "
                        "behavior'.\n\n"
                        "protectedFiles must never include the editable implementation source "
                        "file itself, such as test.py, main.py, test.cpp, or main.cpp. "
                        "Those files are optimization targets, not protected artifacts.\n\n"
                        f"{contract_test_instruction}\n\n"
                        f"{_contract_test_instruction_extra()}\n\n"
                        "If the entrypoint reads its input from stdin, also populate "
                        "benchmarkScaling with a small family of valid inputs at increasing "
                        "problem sizes: 2 to 4 entries, each with the declared size and the "
                        "exact stdin content. Sizes must increase, must be larger than the "
                        "trivial case, and each input must satisfy every input constraint you "
                        "found. These inputs are measured, so they must be deterministic and "
                        "must not be so large that a run takes more than a few seconds. Leave "
                        "benchmarkScaling empty when the program does not read stdin or when "
                        "you cannot construct valid inputs.\n\n"
                        f"{benchmark_harness_instruction}\n\n"
                        f"Language: {language}\n\nProject snapshot:\n{snapshot}\n\n"
                        f"JSON schema:\n{schema}"
                    ),
                ),
            ),
            response_format={"type": "json_object"},
            timeout_seconds=180,
            metadata={"stage": "contract_discovery"},
        )
        previous_error: str | None = None
        for attempt in range(3):
            messages = request.messages
            if previous_error is not None:
                messages = (
                    *messages,
                    Message(
                        role="user",
                        content=(
                            "Your previous response was invalid: "
                            f"{previous_error}\n"
                            "Return only the corrected ProjectContract JSON object."
                        ),
                    ),
                )
            attempt_request = replace(
                request,
                request_id=f"req_{uuid4().hex}",
                messages=messages,
            )
            try:
                response = await self._complete_model(
                    provider,
                    attempt_request,
                    project_root=project_root,
                    stage="contract_discovery",
                    turn=attempt + 1,
                )
                return _parse_contract(response.text)
            except ProviderError:
                return _fallback_contract(project_root, language)
            except ValueError as exc:
                previous_error = str(exc)
        return _fallback_contract(project_root, language)

    async def repair_contract_test(
        self,
        contract: ProjectContract,
        *,
        root: str | Path,
        failure: str,
        language: str = "python",
    ) -> ProjectContract:
        project_root = Path(root).resolve()
        repair_instruction = _repair_contract_test_instruction(language)
        try:
            provider, model = build_provider(
                self._context.config,
                redactor=self._context.secret_redactor,
            )
        except ProviderError:
            return contract
        request = ModelRequest(
            request_id=f"req_{uuid4().hex}",
            model=model,
            system=SYSTEM_RULES,
            messages=(
                Message(
                    role="user",
                    content=(
                        f"Repair the contractTestSource below. {repair_instruction} "
                        f"{_contract_test_instruction_extra()} "
                        'Return JSON only with one field: {"contractTestSource": "..."}.\n\n'
                        "Repair only the test harness. Do not weaken, remove, skip, or "
                        "conditionally "
                        "bypass any testObligations entry to make the test pass. Every public API, "
                        "invariant, state transition, error contract, ordering rule, and "
                        "deterministic "
                        "output must remain covered. Use the reference implementation as the exact "
                        "oracle for expected values and compare observable behavior, not source "
                        "code. "
                        "Exercise stateful workflows after every mutation, including return "
                        "semantics, "
                        "collection/count consistency, structural invariants, and query/iterator "
                        "ordering. If the repair cannot satisfy the full contract, return an empty "
                        "source instead of a weaker test. "
                        "For ordering checks, derive the expected sequence from the reference and "
                        "separately assert the documented sort key. Never preserve a manually "
                        "written "
                        "expected list that contradicts the contract. "
                        "Use the original implementation in .algocode/oracle/reference/ to "
                        "compute expected values; do not hardcode deterministic indices, "
                        "matches, checksums, or workload outputs. "
                        "Contract:\n"
                        f"{json.dumps(contract.model_dump(by_alias=True), ensure_ascii=False)}"
                        "\n\n"
                        f"Failure:\n{failure}"
                    ),
                ),
            ),
            response_format={"type": "json_object"},
            timeout_seconds=180,
            metadata={"stage": "contract_test_repair"},
        )
        try:
            response = await self._complete_model(
                provider,
                request,
                project_root=project_root,
                stage="contract_test_repair",
            )
            payload = json.loads(response.text)
            source = payload.get("contractTestSource", "")
            if not isinstance(source, str) or not source.strip():
                return contract
        except (ProviderError, ValueError, json.JSONDecodeError):
            return contract
        return contract.model_copy(update={"contract_test_source": source})

    async def repair_benchmark_harness(
        self,
        contract: ProjectContract,
        *,
        root: str | Path,
        failure: str,
        language: str = "python",
    ) -> ProjectContract:
        project_root = Path(root).resolve()
        try:
            provider, model = build_provider(
                self._context.config,
                redactor=self._context.secret_redactor,
            )
        except ProviderError:
            return contract
        repair_instruction = _benchmark_harness_repair_instruction(language)
        request = ModelRequest(
            request_id=f"req_{uuid4().hex}",
            model=model,
            system=SYSTEM_RULES,
            messages=(
                Message(
                    role="user",
                    content=(
                        "Repair benchmarkHarness below. "
                        f"{repair_instruction} "
                        "Keep it self-contained, deterministic, and compatible with "
                        "the existing contract. Return JSON only with one field: "
                        '{"benchmarkHarness": "..."}.\n\n'
                        f"Failure:\n{failure}\n\n"
                        "Current harness:\n"
                        f"{contract.benchmark_harness}"
                    ),
                ),
            ),
            response_format={"type": "json_object"},
            timeout_seconds=180,
            metadata={"stage": "benchmark_harness_repair"},
        )
        try:
            response = await self._complete_model(
                provider,
                request,
                project_root=project_root,
                stage="benchmark_harness_repair",
            )
            payload = json.loads(response.text)
            source = payload.get("benchmarkHarness", "")
            if not isinstance(source, str) or not source.strip():
                return contract
        except (ProviderError, ValueError, json.JSONDecodeError):
            return contract
        return contract.model_copy(update={"benchmark_harness": source})

    async def _complete_model(
        self,
        provider,
        request: ModelRequest,
        *,
        project_root: Path,
        stage: str,
        turn: int = 1,
    ):
        logger = ModelCallLogger(
            ProjectLayout.from_root(project_root).cache_dir / "model-logs",
            redactor=self._context.secret_redactor,
        )
        started = time.perf_counter()
        redacted = self._context.secret_redactor.redact_value(request)
        try:
            response = await provider.complete(redacted)
        except Exception as exc:
            await logger.record(
                scope_id="contract",
                task_id=None,
                phase=stage,
                turn=turn,
                request=redacted,
                duration_ms=model_call_duration_ms(started),
                error=exc,
                traceback_text=model_error_traceback(),
            )
            raise
        await logger.record(
            scope_id="contract",
            task_id=None,
            phase=stage,
            turn=turn,
            request=redacted,
            response=response,
            duration_ms=model_call_duration_ms(started),
        )
        return response


class ContractCompiler:
    """Persist a ProjectContract and derive objective and contract tests."""

    def __init__(self, context) -> None:
        self._context = context

    def compile(
        self,
        root: str | Path,
        contract: ProjectContract,
        language: str = "python",
    ) -> str:
        project_root = Path(root).resolve()
        layout = ProjectLayout.from_root(project_root)
        layout.oracle_dir.mkdir(parents=True, exist_ok=True)
        language = language.lower()
        contract = _sanitize_contract(contract, project_root, language)
        _copy_reference_sources(project_root, layout.reference_dir)
        layout.contract_path.write_text(
            json.dumps(
                contract.model_dump(by_alias=True, mode="json"),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        python_path = layout.contract_test_path
        cpp_path = layout.cpp_contract_test_path
        source = contract.contract_test_source.strip()
        if language == "cpp":
            python_path.unlink(missing_ok=True)
            if source:
                cpp_path.write_text(source + "\n", encoding="utf-8")
            else:
                cpp_path.unlink(missing_ok=True)
        else:
            cpp_path.unlink(missing_ok=True)
            if source:
                python_path.write_text(
                    _normalize_contract_test_source(source),
                    encoding="utf-8",
                )
            else:
                python_path.unlink(missing_ok=True)
        return contract_to_objective(contract, language=language)


def _sanitize_contract(
    contract: ProjectContract,
    project_root: Path,
    language: str,
) -> ProjectContract:
    suffixes = {".py"} if language == "python" else {".cpp", ".cc", ".cxx", ".c++"}
    implementation_paths = {
        path.relative_to(project_root).as_posix()
        for path in project_root.iterdir()
        if path.is_file() and path.suffix.lower() in suffixes
    }
    if not implementation_paths:
        return contract
    protected: list[str] = []
    removed = False
    for item in contract.protected_files:
        normalized = item.replace("\\", "/").lstrip("./").rstrip("/")
        if any(fnmatch.fnmatchcase(path, normalized) for path in implementation_paths):
            removed = True
            continue
        protected.append(item)
    if not removed:
        return contract
    return contract.model_copy(update={"protected_files": tuple(protected)})


def _copy_reference_sources(project_root: Path, reference_dir: Path) -> None:
    reference_dir.mkdir(parents=True, exist_ok=True)
    suffixes = {".py", ".cpp", ".cc", ".cxx", ".c++"}
    sources = {
        path.name: path
        for path in sorted(project_root.iterdir())
        if path.is_file() and path.suffix.lower() in suffixes
    }
    for filename, source in sources.items():
        (reference_dir / filename).write_bytes(source.read_bytes())
    for existing in reference_dir.iterdir():
        if existing.name not in sources:
            existing.unlink()


def _contract_test_path(language: str) -> str:
    if language == "cpp":
        return ".algocode/oracle/contract_test.cpp"
    return ".algocode/oracle/contract_test.py"


def _contract_test_instruction(language: str) -> str:
    if language == "cpp":
        return (
            "contractTestSource must be a standalone C++17 program that executes every "
            "testObligations entry. It will be saved as .algocode/oracle/contract_test.cpp. "
            "The runner compiles the same harness twice: once with the candidate root on "
            "the include path and once with .algocode/oracle/reference on the include path. "
            "The harness must include the primary implementation using an include directive "
            "for the root source filename after temporarily renaming `main` with the "
            "preprocessor. The harness must define its own `int main()`, print a "
            "deterministic transcript or checksum, avoid elapsed/time/address/container-order "
            "output, and return non-zero on any failed assertion. Do not hardcode values "
            "that the same harness can compute from the reference build. Do not use network "
            "access. Return JSON only."
        )
    return (
        "contractTestSource must be a standalone Python script that executes every "
        "testObligations entry. It must import the candidate module and the original "
        "reference copy under .algocode/oracle/reference/. Use the reference as an oracle "
        "for deterministic comparisons. Exercise all relevant public APIs, including "
        "stateful workflows, randomized operation sequences, negative cases, boundary "
        "inputs, return values, exceptions, ordering, and state after each mutation. "
        "Do not weaken, omit, or conditionally bypass an obligation. Exit non-zero on any "
        "missing API, mismatch, unsorted result, invariant violation, or unexpected "
        "exception. Never hardcode values that the reference can compute. The script will "
        "be executed as .algocode/oracle/contract_test.py from the project root. Resolve "
        "the project root as Path(__file__).resolve().parents[2]. Do not use network "
        "access. Return JSON only."
    )


def _contract_test_instruction_extra() -> str:
    return (
        "Do not determine project files by checking whether '.algocode' appears in "
        "an absolute path's parts. Candidate worktrees can themselves live under a "
        "data directory named .algocode. When filtering files returned by "
        "ROOT.rglob(), inspect the path relative to ROOT: "
        "relative = path.relative_to(ROOT); if '.algocode' not in relative.parts. "
        "Never use 'path.parts' directly for this check."
    )


def _repair_contract_test_instruction(language: str) -> str:
    if language == "cpp":
        return (
            "It must remain a standalone C++17 harness at "
            ".algocode/oracle/contract_test.cpp and will be compiled separately against "
            "candidate and reference roots. Preserve the main-renaming include pattern and "
            "deterministic output contract."
        )
    return (
        "It must remain a standalone Python script at .algocode/oracle/contract_test.py "
        "and continue to use the reference copy as its oracle."
    )


def _benchmark_harness_instruction(language: str) -> str:
    if language == "cpp":
        return (
            "When this is a single-file C++17 project whose root implementation file "
            "defines main, populate benchmarkHarness with one complete C++17 harness. "
            "The harness must define main as algocode_original_main before including the "
            "root implementation source by filename, undefine main, and then define its "
            "own int main(int argc, char** argv). Parse the round count from argv[1] with "
            "a default of 1000, build deterministic varying inputs, and repeatedly exercise "
            "the core public APIs in a loop. Print exactly one line of the form "
            "'rounds=<n> workload=<seconds>s' and exit 0. The harness must be self-contained, "
            "compile with C++17, read nothing from stdin, and use no network. Leave "
            "benchmarkHarness empty for multi-file C++ projects or when the implementation "
            "cannot be safely included in one translation unit.\n\n"
        )
    return (
        "For Python projects, most programs finish their real workload in microseconds "
        "while starting the interpreter costs tens of milliseconds, so timing the whole "
        "process measures start-up instead of the code. When the module exposes "
        "lower-level public APIs, populate benchmarkHarness with one complete, "
        "self-contained Python script that imports the module once, builds a "
        "deterministic set of multiple input cases, and exercises those APIs with "
        "varying inputs on every iteration. Do not repeat one identical deterministic "
        "call with the same constant arguments, because that lets a global result cache "
        "replace the measured work. Prefer direct calls to core public APIs over "
        "repeatedly calling one fixed workload wrapper. The script must take the "
        "iteration count from sys.argv[1], default to 1000, read nothing from stdin, "
        "print exactly one line of the form 'rounds=<n> workload=<seconds>s', and exit "
        "0. Set a module into sys.modules before exec_module when loading by path. "
        "Leave benchmarkHarness empty for other languages, or when no suitable public "
        "APIs exist.\n\n"
    )


def _benchmark_harness_repair_instruction(language: str) -> str:
    if language == "cpp":
        return (
            "Return C++17 source for a single-file project. It must vary input on every "
            "iteration and must not repeatedly call one deterministic function with identical "
            "constant arguments. Define main as algocode_original_main, include the root "
            "implementation source by filename, undefine main, and define its own "
            "int main(int argc, char** argv). Parse rounds from argv[1] with a default of "
            "1000, call core public APIs directly, print exactly one line of the form "
            "'rounds=<n> workload=<seconds>s', and exit 0. The source must compile as a "
            "single translation unit with C++17 and must not read stdin or use network access."
        )
    return (
        "It must vary input on every iteration and must not repeatedly call one "
        "deterministic entrypoint with identical constant arguments. Prefer direct calls "
        "to the core public APIs over a fixed workload wrapper. Keep it self-contained, "
        "deterministic, Python, and compatible with the existing contract."
    )


def contract_to_objective(
    contract: ProjectContract,
    *,
    language: str = "python",
) -> str:
    lines = [
        contract.purpose.strip(),
        "",
        f"Performance goal: {contract.performance_goal.strip()}",
    ]
    if contract.public_api:
        lines.extend(["", "Public API obligations:"])
        lines.extend(
            f"- {item.symbol}: {item.signature or '(signature not specified)'} -> "
            f"{item.behavior or '(behavior not specified)'}"
            for item in contract.public_api
        )
    if contract.state_transitions:
        lines.extend(["", "State transitions:"])
        lines.extend(f"- {item}" for item in contract.state_transitions)
    if contract.error_contracts:
        lines.extend(["", "Error contracts:"])
        lines.extend(f"- {item}" for item in contract.error_contracts)
    deterministic_outputs = contract.observable_outputs.deterministic
    if deterministic_outputs:
        lines.extend(["", "Deterministic outputs:"])
        lines.extend(f"- {item}" for item in deterministic_outputs)
    if contract.invariants:
        lines.extend(["", "Invariants:"])
        lines.extend(f"- {item}" for item in contract.invariants)
    if contract.must_not_change:
        lines.extend(["", "Must not change:"])
        lines.extend(f"- {item}" for item in contract.must_not_change)
    if contract.test_obligations:
        lines.extend(["", "Executable test obligations:"])
        lines.extend(
            f"- [{item.kind}] {item.target}: {item.assertion}" for item in contract.test_obligations
        )
    lines.extend(
        [
            "",
            "Contract compliance (hard constraints):",
            "- Performance changes must never remove, weaken, or bypass a behavior contract.",
            "- Exact return values, ordering, tie-breaking, errors, state transitions, invariants, "
            "and deterministic outputs are mandatory.",
            "- Before editing, identify every public API, state transition, and invariant affected "
            "by the change.",
            "- After editing, run every test obligation, correctness check, and candidate check.",
            "- Do not replace or weaken a required check just to obtain a speedup.",
            "- If performance and contract cannot both be satisfied, stop and report the blocker.",
        ]
    )
    lines.extend(["", "Protected files:"])
    protected = contract.protected_files or (
        ".algocode/oracle/",
        ".algocode/benchmarks/",
        ".algocode/config.yaml",
    )
    lines.extend(f"- {item}" for item in protected)
    lines.extend(
        [
            "- Implementation source files are editable unless explicitly listed protected.",
        ]
    )
    lines.extend(
        [
            "",
            "Use .algocode/oracle/correctness.yaml for output correctness and "
            f"{_contract_test_path(language)} for behavior-contract verification when present.",
        ]
    )
    return "\n".join(line for line in lines if line is not None).strip()


def _source_snapshot(root: Path) -> str:
    chunks: list[str] = []
    total = 0
    for relative in discover_required_files(root):
        path = root / relative
        try:
            raw = path.read_bytes()
        except OSError:
            continue
        if len(raw) > MAX_CONTRACT_FILE_BYTES:
            raw = raw[:MAX_CONTRACT_FILE_BYTES]
        text = raw.decode("utf-8", errors="replace")
        chunk = f"\n--- FILE: {relative} ---\n{text}\n"
        if total + len(chunk.encode("utf-8")) > MAX_CONTRACT_SOURCE_BYTES:
            break
        chunks.append(chunk)
        total += len(chunk.encode("utf-8"))
    return "".join(chunks)


def benchmark_harness_issue(source: str, *, language: str = "python") -> str | None:
    """Reject harnesses whose fixed loop can be replaced by one cached result."""

    if not source.strip():
        return None
    if language == "cpp":
        return _cpp_benchmark_harness_issue(source)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return f"benchmarkHarness is not valid Python: {exc}"

    for loop in (node for node in ast.walk(tree) if isinstance(node, (ast.For, ast.While))):
        loop_targets = _loop_target_names(loop)
        for call in _repeated_loop_calls(loop):
            name = _call_name(call)
            if not name or _is_allowed_benchmark_constant_call(name):
                continue
            if _call_depends_on_loop_target(call, loop_targets):
                continue
            argument_nodes = [*call.args, *(keyword.value for keyword in call.keywords)]
            if not argument_nodes:
                continue
            if not any(
                isinstance(node, ast.Name)
                for argument in argument_nodes
                for node in ast.walk(argument)
            ):
                return (
                    f"benchmarkHarness repeatedly calls {name} with constant arguments "
                    "inside a loop; vary inputs or call lower-level APIs instead"
                )
    return None


def _cpp_benchmark_harness_issue(source: str) -> str | None:
    required_markers = (
        ("#define main ", "define main as algocode_original_main before including source"),
        ('#include "', "include the root implementation source by filename"),
        ("#undef main", "undefine main before defining the harness entrypoint"),
        ("int main(", "define the harness int main entrypoint"),
    )
    for marker, description in required_markers:
        if marker not in source:
            return f"benchmarkHarness must {description}; missing {marker!r}"
    return None


_BENCHMARK_HARNESS_ALLOWED_CONSTANT_CALLS = {
    "dict",
    "float",
    "int",
    "len",
    "list",
    "perf_counter",
    "print",
    "range",
    "set",
    "str",
    "time.perf_counter",
}

_BENCHMARK_HARNESS_STATEFUL_RANDOM_METHODS = {
    "choice",
    "choices",
    "getrandbits",
    "randbytes",
    "randint",
    "randrange",
    "random",
    "sample",
    "shuffle",
    "uniform",
}


def _loop_target_names(loop: ast.For | ast.While) -> set[str]:
    if isinstance(loop, ast.For):
        return {node.id for node in ast.walk(loop.target) if isinstance(node, ast.Name)}
    return set()


def _repeated_loop_calls(loop: ast.For | ast.While):
    statements: list[ast.AST] = [*loop.body]
    if isinstance(loop, ast.While):
        statements.insert(0, loop.test)
    for statement in statements:
        yield from _calls_outside_nested_loops(statement)


def _calls_outside_nested_loops(node: ast.AST):
    if isinstance(node, (ast.For, ast.While)):
        return
    if isinstance(node, ast.Call):
        yield node
    for child in ast.iter_child_nodes(node):
        yield from _calls_outside_nested_loops(child)


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        prefix = call.func.value.id if isinstance(call.func.value, ast.Name) else None
        return f"{prefix}.{call.func.attr}" if prefix else call.func.attr
    return None


def _is_allowed_benchmark_constant_call(name: str) -> bool:
    if name in _BENCHMARK_HARNESS_ALLOWED_CONSTANT_CALLS:
        return True
    method = name.rsplit(".", 1)[-1]
    return method in _BENCHMARK_HARNESS_STATEFUL_RANDOM_METHODS


def _call_depends_on_loop_target(call: ast.Call, targets: set[str]) -> bool:
    if not targets:
        return False
    return any(
        isinstance(node, ast.Name) and node.id in targets
        for node in ast.walk(call)
    )


def _normalize_contract_test_source(source: str) -> str:
    normalized = source.strip()
    normalized = re.sub(
        r"([\"']\.algocode[\"']\s+not\s+in\s+)([A-Za-z_]\w*)\.parts",
        r"\1\2.relative_to(ROOT).parts",
        normalized,
    )
    replacements = {
        'Path(__file__).resolve().parent / "test.py"': (
            'Path(__file__).resolve().parents[2] / "test.py"'
        ),
        "Path(__file__).resolve().parent / 'test.py'": (
            "Path(__file__).resolve().parents[2] / 'test.py'"
        ),
        'Path(__file__).parent / "test.py"': 'Path(__file__).resolve().parents[2] / "test.py"',
        "Path(__file__).parent / 'test.py'": "Path(__file__).resolve().parents[2] / 'test.py'",
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized + "\n"


def _parse_contract(text: str) -> ProjectContract:
    return parse_model(text, ProjectContract, label="contract response")


def _fallback_contract(root: Path, language: str) -> ProjectContract:
    symbols = _fallback_public_api(root) if language == "python" else ()
    return ProjectContract(
        purpose="Preserve observable behavior while optimizing the primary algorithm.",
        entrypoints=(),
        public_api=tuple(
            PublicApiItem(symbol=symbol, behavior="public API discovered by AST")
            for symbol in symbols
        ),
        invariants=(
            "Public API signatures and documented behavior must remain stable.",
            "Configuration fields must retain their documented semantics.",
            "Errors and state transitions must remain compatible.",
        ),
        performance_goal="Reduce wall-clock runtime of the primary entrypoint.",
        must_not_change=(
            "public API signatures",
            "configuration field semantics",
            "error behavior",
            "observable deterministic outputs",
        ),
        protected_files=(
            ".algocode/oracle/",
            ".algocode/benchmarks/",
            ".algocode/config.yaml",
        ),
        confidence=0.5,
        contract_source="deterministic-fallback",
    )


def _fallback_public_api(root: Path) -> tuple[str, ...]:
    import ast

    symbols: set[str] = set()
    for path in sorted(root.glob("*.py")):
        if path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
        for node in tree.body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                symbols.add(node.name)
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                symbols.add(node.name)
                for child in node.body:
                    if isinstance(
                        child, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ) and not child.name.startswith("_"):
                        symbols.add(f"{node.name}.{child.name}")
    return tuple(sorted(symbols))

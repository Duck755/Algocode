"""Model-driven project contract discovery and compilation."""

from __future__ import annotations

import fnmatch
import json
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


def _normalize_contract_test_source(source: str) -> str:
    normalized = source.strip()
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

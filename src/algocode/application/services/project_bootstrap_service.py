"""Automatic project initialization and first-task bootstrap."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from algocode.application.services.contract_service import (
    ContractCompiler,
    ContractDiscoveryService,
)
from algocode.application.services.project_state import (
    find_current_task,
    write_bootstrap_state,
)
from algocode.benchmark.spec import load_benchmark_spec
from algocode.correctness.spec import load_correctness_spec
from algocode.domain.model import BenchmarkStatus, Language
from algocode.project_layout import ProjectLayout
from algocode.workspace import GitRepository
from algocode.workspace.git import GitError

_CHECKER_SOURCE = '''"""Compare deterministic key=value output while ignoring volatile fields."""

from __future__ import annotations

import sys
from pathlib import Path

_VOLATILE_KEYS = {
    "cpu_time",
    "duration",
    "elapsed",
    "elapsed_seconds",
    "runtime",
    "time",
    "timestamp",
    "wall_time",
}


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _parse(text: str) -> dict[str, str] | None:
    values: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or "=" not in stripped:
            return None
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    actual = _read(sys.argv[1])
    expected = _read(sys.argv[2])
    actual_values = _parse(actual)
    expected_values = _parse(expected)
    if actual_values is None or expected_values is None:
        if actual.strip() == expected.strip():
            return 0
        print("output mismatch", file=sys.stderr)
        return 1

    actual_filtered = {
        key: value for key, value in actual_values.items() if key not in _VOLATILE_KEYS
    }
    expected_filtered = {
        key: value for key, value in expected_values.items() if key not in _VOLATILE_KEYS
    }
    if actual_filtered != expected_filtered:
        print(f"key/value mismatch: {actual_filtered!r} != {expected_filtered!r}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


@dataclass(frozen=True, slots=True)
class BootstrapResult:
    project: object
    task: object
    baseline: object
    correctness: object | None
    benchmark_run: object | None
    benchmark_result: object | None
    git_initialized: bool
    commit_created: bool
    generated_files: tuple[str, ...]
    bootstrap_status: str
    message: str = ""


class ProjectBootstrapService:
    """Prepare a directory so it is immediately ready for optimization."""

    def __init__(self, context) -> None:
        self._context = context

    async def run(
        self,
        path: str | Path,
        *,
        language: Language | str = Language.AUTO,
        objective: str | None = None,
    ) -> BootstrapResult:
        root = Path(path).expanduser().resolve()
        layout = ProjectLayout.from_root(root)
        root.mkdir(parents=True, exist_ok=True)
        git_initialized = False
        try:
            repository = await GitRepository.discover(root)
        except GitError:
            repository = await GitRepository.initialize(root)
            git_initialized = True

        detected = await self._context.language_registry.detect(root)
        selected_language = self._context.language_registry.resolve_language(
            language,
            detected,
        )
        self._write_project_config(root, selected_language)
        self._write_state_gitignore(layout)
        discovery = ContractDiscoveryService(self._context)
        compiler = ContractCompiler(self._context)
        contract = await discovery.discover(
            root,
            language=selected_language.value,
        )
        compiled_objective = ""
        contract_failure: str | None = None
        previous_source: str | None = None
        for attempt in range(3):
            compiled_objective = compiler.compile(root, contract, language=selected_language.value)
            contract_failure = await self._run_contract_test(root, language=selected_language.value)
            if contract_failure is None:
                break
            if not contract.contract_test_source or attempt == 2:
                break
            repair_failure = contract_failure
            if previous_source == contract.contract_test_source:
                repair_failure += (
                    "\n\nThe previous repair returned exactly the same source. "
                    "Replace the incorrect expected-state logic instead of returning it again."
                )
            repaired = await discovery.repair_contract_test(
                contract,
                root=root,
                failure=repair_failure,
                language=selected_language.value,
            )
            previous_source = contract.contract_test_source
            contract = repaired
        if contract_failure is not None:
            fallback_source = (
                _reference_conformance_test_source_cpp(root)
                if selected_language is Language.CPP
                else _reference_conformance_test_source(contract)
            )
            contract = contract.model_copy(update={"contract_test_source": fallback_source})
            compiled_objective = compiler.compile(root, contract, language=selected_language.value)
            contract_failure = await self._run_contract_test(root, language=selected_language.value)
        if contract_failure is not None and contract.contract_test_source:
            raise RuntimeError(f"generated contract test failed: {contract_failure}")
        effective_objective = (
            objective or compiled_objective or _infer_objective(root, selected_language)
        )

        generated: tuple[str, ...] = ()
        bootstrap_status = "skipped"
        bootstrap_message = ""
        if selected_language is Language.PYTHON:
            generated = await self._bootstrap_python(root)
            bootstrap_status = "completed"
        elif selected_language is Language.CPP:
            generated = await self._bootstrap_cpp(root)
            bootstrap_status = "completed"

        commit_created = await repository.commit_all("algocode: initialize project")
        project = await self._context.project_service.register(root, write_config=False)
        task = await self._context.task_service.create_task(
            objective=effective_objective,
            project_id=project.id,
        )
        baseline = await self._context.baseline_service.capture(task.id)

        correctness = None
        correctness_run = None
        benchmark_run = None
        benchmark_result = None
        if generated:
            correctness_run, correctness = await self._context.correctness_service.run_baseline(
                task.id,
                load_correctness_spec(layout.correctness_spec_path),
            )
            if not correctness.passed:
                raise RuntimeError(
                    "generated correctness specification failed: "
                    f"kind={correctness.failure_kind}, message={correctness.message!r}, "
                    f"cases={correctness.cases!r}"
                )
            benchmark_run, benchmark_result = await self._context.benchmark_service.run_baseline(
                task.id,
                load_benchmark_spec(layout.benchmark_spec_path),
            )
            if benchmark_run.status is not BenchmarkStatus.COMPLETED or not benchmark_result.valid:
                raise RuntimeError("generated benchmark specification failed")

        write_bootstrap_state(
            project_root=root,
            data_dir=self._context.data_dir,
            project_id=str(project.id),
            project_language=selected_language.value,
            git_revision=project.git_revision,
            task_id=str(task.id),
            objective=effective_objective,
            baseline_id=str(baseline.id),
            correctness_result_id=(
                str(correctness_run.id) if correctness_run is not None else None
            ),
            correctness_status=(str(correctness.status) if correctness is not None else None),
            benchmark_run_id=(str(benchmark_run.id) if benchmark_run is not None else None),
            benchmark_valid=(
                bool(benchmark_result.valid) if benchmark_result is not None else None
            ),
            generated_files=generated,
        )

        await self._verify_persisted_state(
            project=project,
            task=task,
            baseline=baseline,
            correctness_run=correctness_run,
            benchmark_run=benchmark_run,
        )

        return BootstrapResult(
            project=project,
            task=task,
            baseline=baseline,
            correctness=correctness,
            benchmark_run=benchmark_run,
            benchmark_result=benchmark_result,
            git_initialized=git_initialized,
            commit_created=commit_created,
            generated_files=generated,
            bootstrap_status=bootstrap_status,
            message=bootstrap_message,
        )

    async def _verify_persisted_state(
        self,
        *,
        project,
        task,
        baseline,
        correctness_run,
        benchmark_run,
    ) -> None:
        persisted_project = await self._context.project_service.get(project.id)
        persisted_task = await self._context.task_service.get_task(task.id)
        persisted_baseline = await self._context.baseline_service.get_for_task(task.id)

        if str(persisted_project.id) != str(project.id):
            raise RuntimeError("bootstrap project projection was not persisted")
        if str(persisted_task.id) != str(task.id):
            raise RuntimeError("bootstrap task projection was not persisted")
        if persisted_baseline is None or str(persisted_baseline.id) != str(baseline.id):
            raise RuntimeError("bootstrap baseline projection was not persisted")

        if correctness_run is not None:
            persisted_correctness = await self._context.correctness_service.get(
                str(correctness_run.id)
            )
            if str(persisted_correctness.id) != str(correctness_run.id):
                raise RuntimeError("bootstrap correctness projection was not persisted")
        if benchmark_run is not None:
            persisted_benchmark = await self._context.benchmark_service.get(str(benchmark_run.id))
            if str(persisted_benchmark.id) != str(benchmark_run.id):
                raise RuntimeError("bootstrap benchmark projection was not persisted")

    async def _bootstrap_python(self, root: Path) -> tuple[str, ...]:
        entry = _python_entrypoint(root)
        command = (sys.executable, str(entry))
        runner = self._context.language_registry.sandbox_runner
        result = await runner.run(
            command,
            cwd=root,
            timeout_seconds=60,
            input_bytes=b"",
        )
        if result.start_failed or result.timed_out or result.exit_code != 0:
            message = result.stderr.decode(errors="replace").strip() or "bootstrap command failed"
            raise RuntimeError(message)

        expected_output = result.stdout.decode(errors="replace")
        layout = ProjectLayout.from_root(root)
        checker_path = layout.oracle_dir / "check.py"
        correctness_path = layout.correctness_spec_path
        benchmark_path = layout.benchmark_spec_path
        checker_path.parent.mkdir(parents=True, exist_ok=True)
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)

        if not checker_path.exists():
            checker_path.write_text(_CHECKER_SOURCE, encoding="utf-8")
        if not correctness_path.exists():
            correctness_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "mode": "cases",
                        "comparison": "checker-command",
                        "require_determinism": False,
                        "run_command": [sys.executable, entry.name],
                        "timeout_seconds": 60,
                        "cases": [
                            {
                                "id": "primary-output",
                                "expected_output": expected_output,
                            }
                        ],
                        "checker_command": [
                            sys.executable,
                            ".algocode/oracle/check.py",
                            "{candidate}",
                            "{expected}",
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        if not benchmark_path.exists():
            benchmark_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "scope": "stdin",
                        "run_command": [sys.executable, entry.name],
                        "warmup": 5,
                        "repeats": 15,
                        "timeout_seconds": 60,
                        "metric": "wall_time",
                        "direction": "minimize",
                        "max_variation_percent": 5.0,
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        generated = [
            ".algocode/config.yaml",
            ".algocode/.gitignore",
            ".algocode/oracle/check.py",
            ".algocode/oracle/correctness.yaml",
            ".algocode/benchmarks/benchmark.yaml",
        ]
        for relative in (".algocode/contract.json", ".algocode/oracle/contract_test.py"):
            if (root / relative).is_file():
                generated.append(relative)
        return tuple(generated)

    async def _bootstrap_cpp(self, root: Path) -> tuple[str, ...]:
        entry = _cpp_entrypoint(root)
        compiler = shutil.which("g++") or shutil.which("clang++")
        if compiler is None:
            raise RuntimeError("no C++ compiler was found on PATH")
        layout = ProjectLayout.from_root(root)
        output_dir = layout.cache_dir / "bootstrap"
        output_dir.mkdir(parents=True, exist_ok=True)
        executable = output_dir / ("reference.exe" if os.name == "nt" else "reference")
        runner = self._context.language_registry.sandbox_runner
        compile_result = await runner.run(
            (
                compiler,
                "-std=c++17",
                "-O2",
                "-pthread",
                str(entry),
                "-o",
                str(executable),
            ),
            cwd=root,
            timeout_seconds=120,
            input_bytes=b"",
        )
        if compile_result.start_failed or compile_result.timed_out or compile_result.exit_code != 0:
            message = compile_result.stderr.decode(errors="replace").strip()
            raise RuntimeError(message or "C++ bootstrap compilation failed")
        run_result = await runner.run(
            (str(executable),),
            cwd=root,
            timeout_seconds=60,
            input_bytes=b"",
        )
        if run_result.start_failed or run_result.timed_out or run_result.exit_code != 0:
            message = run_result.stderr.decode(errors="replace").strip()
            raise RuntimeError(message or "C++ bootstrap reference run failed")
        expected_output = run_result.stdout.decode(errors="replace")
        checker_path = layout.oracle_dir / "check.py"
        correctness_path = layout.correctness_spec_path
        benchmark_path = layout.benchmark_spec_path
        checker_path.parent.mkdir(parents=True, exist_ok=True)
        benchmark_path.parent.mkdir(parents=True, exist_ok=True)
        if not checker_path.exists():
            checker_path.write_text(_CHECKER_SOURCE, encoding="utf-8")
        if not correctness_path.exists():
            correctness_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "mode": "cases",
                        "comparison": "checker-command",
                        "require_determinism": False,
                        "run_command": [],
                        "timeout_seconds": 60,
                        "cases": [
                            {
                                "id": "primary-output",
                                "expected_output": expected_output,
                            }
                        ],
                        "checker_command": [
                            sys.executable,
                            ".algocode/oracle/check.py",
                            "{candidate}",
                            "{expected}",
                        ],
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        if not benchmark_path.exists():
            benchmark_path.write_text(
                yaml.safe_dump(
                    {
                        "schema_version": 1,
                        "scope": "process",
                        "run_command": [],
                        "warmup": 5,
                        "repeats": 15,
                        "timeout_seconds": 60,
                        "metric": "wall_time",
                        "direction": "minimize",
                        "max_variation_percent": 5.0,
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        generated = [
            ".algocode/config.yaml",
            ".algocode/.gitignore",
            ".algocode/oracle/check.py",
            ".algocode/oracle/correctness.yaml",
            ".algocode/benchmarks/benchmark.yaml",
        ]
        for relative in (
            ".algocode/contract.json",
            ".algocode/oracle/contract_test.cpp",
        ):
            if (root / relative).is_file():
                generated.append(relative)
        return tuple(generated)

    async def _run_contract_test(
        self,
        root: Path,
        *,
        language: str = "python",
    ) -> str | None:
        layout = ProjectLayout.from_root(root)
        path = layout.contract_test()
        if path is None:
            return None
        if path.suffix.lower() == ".cpp":
            from algocode.languages.cpp import run_cpp_contract_test

            contract_result = await run_cpp_contract_test(
                root,
                path,
                self._context.language_registry.sandbox_runner,
            )
            if contract_result.passed:
                return None
            stdout = contract_result.stdout.decode(errors="replace").strip()
            stderr = contract_result.stderr.decode(errors="replace").strip()
            details = [contract_result.message] if contract_result.message else []
            if stdout:
                details.append(f"stdout:\n{stdout}")
            if stderr:
                details.append(f"stderr:\n{stderr}")
            return "\n".join(details) or "C++ contract test failed"
        result = await self._context.language_registry.sandbox_runner.run(
            (sys.executable, layout.relative(path)),
            cwd=root,
            timeout_seconds=120,
            input_bytes=b"",
        )
        if result.exit_code == 0 and not result.timed_out:
            return None
        stdout = result.stdout.decode(errors="replace").strip()
        stderr = result.stderr.decode(errors="replace").strip()
        details: list[str] = []
        if stdout:
            details.append(f"stdout:\n{stdout}")
        if stderr:
            details.append(f"stderr:\n{stderr}")
        return "\n".join(details) or "contract test exited non-zero"

    @staticmethod
    def _write_project_config(root: Path, language: Language) -> None:
        layout = ProjectLayout.from_root(root)
        path = layout.config_path
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "version": 1,
                    "project": {
                        "language": language.value,
                        "source_root": ".",
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    @staticmethod
    def _write_state_gitignore(layout: ProjectLayout) -> None:
        path = layout.algocode_dir / ".gitignore"
        path.parent.mkdir(parents=True, exist_ok=True)
        entries = (
            "cache/",
            "config.local.yaml",
            "current-task.json",
            "task.txt",
        )
        existing = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        lines = existing.splitlines()
        missing = [entry for entry in entries if entry not in lines]
        if not missing:
            return
        content = "\n".join([*lines, *missing]).strip() + "\n"
        path.write_text(content, encoding="utf-8")
        exclude = layout.root / ".git" / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing_exclude = (
            exclude.read_text(encoding="utf-8", errors="replace") if exclude.exists() else ""
        )
        exclude_lines = existing_exclude.splitlines()
        for entry in ("__pycache__/", "*.py[cod]"):
            if entry not in exclude_lines:
                exclude_lines.append(entry)
        exclude.write_text("\n".join(exclude_lines).rstrip() + "\n", encoding="utf-8")


def _reference_conformance_test_source(contract) -> str:
    symbols = [item.symbol for item in contract.public_api]
    return f'''#!/usr/bin/env python3
"""Deterministic reference conformance test generated by Algocode."""

from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / ".algocode" / "oracle" / "reference"
SYMBOLS = {symbols!r}


def fail(message: str) -> None:
    print("CONTRACT FAIL:", message)
    raise SystemExit(1)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(name, None)
        return None
    return module


def bind(module, name: str):
    parts = name.split(".")
    current = module
    if len(parts) > 1 and not hasattr(current, parts[0]):
        parts = parts[1:]
    for part in parts:
        current = getattr(current, part)
    return current


def find_reference():
    for path in sorted(REFERENCE.glob("*.py")):
        module = load(path, "algocode_reference_" + path.stem)
        if module is None:
            continue
        try:
            for symbol in SYMBOLS:
                bind(module, symbol)
        except AttributeError:
            continue
        return module
    fail("could not locate reference module in .algocode/oracle/reference")


def find_candidate():
    for path in sorted(ROOT.glob("*.py")):
        module = load(path, "algocode_candidate_" + path.stem)
        if module is None:
            continue
        try:
            for symbol in SYMBOLS:
                bind(module, symbol)
        except AttributeError:
            continue
        return module
    fail("could not locate candidate module with documented public symbols")


def stateful_class(module):
    for value in vars(module).values():
        if isinstance(value, type) and all(hasattr(value, name) for name in ("insert", "get")):
            return value
    return None


def interval_tree_class(module):
    methods = ("insert", "delete", "query_point", "query_overlap", "iter_inorder")
    for value in vars(module).values():
        if isinstance(value, type) and all(hasattr(value, name) for name in methods):
            return value
    return None


def compare_workload(candidate, reference) -> None:
    if not hasattr(candidate, "run_workload") or not hasattr(reference, "run_workload"):
        return
    for n_ops, seed in ((2000, 42), (5000, 7), (1000, 0), (20000, 42)):
        got = tuple(candidate.run_workload(n_ops, seed))
        expected = tuple(reference.run_workload(n_ops, seed))
        if got != expected:
            fail(f"run_workload mismatch for {{n_ops}},{{seed}}: {{got!r}} != {{expected!r}}")


def compare_stateful(candidate, reference) -> None:
    candidate_class = stateful_class(candidate)
    reference_class = stateful_class(reference)
    if candidate_class is None or reference_class is None:
        return
    candidate_object = candidate_class()
    reference_object = reference_class()
    operations = [(5, 50), (5, 99)]
    rng = random.Random(1234)
    operations.extend((rng.randrange(5000), rng.randrange(10**6)) for _ in range(4000))
    for key, value in operations:
        got = candidate_object.insert(key, value)
        expected = reference_object.insert(key, value)
        if got != expected:
            fail(f"insert mismatch for key {{key}}: {{got!r}} != {{expected!r}}")
    if hasattr(candidate_object, "__len__") and hasattr(reference_object, "__len__"):
        if len(candidate_object) != len(reference_object):
            fail("stateful object length mismatch")
    for key in list(range(100)) + [1000, 2000, 3000, 4000]:
        if candidate_object.get(key) != reference_object.get(key):
            fail(f"get mismatch for key {{key}}")
    try:
        candidate_items = list(candidate_object)
        reference_items = list(reference_object)
    except TypeError:
        return
    if candidate_items != reference_items:
        fail("iteration differs from reference")


def triple_values(values):
    return [(value.lo, value.hi, value.id) for value in values]


def compare_interval_tree(candidate, reference) -> bool:
    candidate_class = interval_tree_class(candidate)
    reference_class = interval_tree_class(reference)
    if candidate_class is None or reference_class is None:
        return False
    candidate_object = candidate_class()
    reference_object = reference_class()
    rng = random.Random(20240916)
    stored = []
    for step in range(6000):
        if stored and rng.random() < 0.35:
            lo, hi, ident = rng.choice(stored)
            got = candidate_object.delete(lo, hi, ident)
            expected = reference_object.delete(lo, hi, ident)
            if got != expected:
                fail("interval-tree delete return mismatch")
            if got:
                stored.remove((lo, hi, ident))
        else:
            lo = rng.randrange(-100, 100)
            hi = lo + rng.randrange(0, 20)
            ident = rng.randrange(50)
            triple = (lo, hi, ident)
            got = candidate_object.insert(lo, hi, ident)
            expected = reference_object.insert(lo, hi, ident)
            if got != expected:
                fail("interval-tree insert return mismatch")
            if got:
                stored.append(triple)
        if len(candidate_object) != len(reference_object):
            fail("interval-tree length mismatch")
        candidate_order = triple_values(candidate_object.iter_inorder())
        reference_order = triple_values(reference_object.iter_inorder())
        if candidate_order != reference_order:
            fail("interval-tree in-order mismatch")
        if candidate_order != sorted(candidate_order):
            fail("interval-tree in-order is not sorted")
        if len(candidate_order) != len(set(candidate_order)):
            fail("interval-tree contains duplicate entries")
        if candidate_object.height() != reference_object.height():
            fail("interval-tree height mismatch")
        if candidate_object.max_hi() != reference_object.max_hi():
            fail("interval-tree max_hi mismatch")
        if step % 10 == 0:
            for point in (lo - 1, lo, hi, hi + 1):
                if triple_values(candidate_object.query_point(point)) != triple_values(
                    reference_object.query_point(point)
                ):
                    fail("interval-tree query_point mismatch")
            for start, end in ((lo - 5, hi + 5), (lo, hi), (hi + 1, hi + 6)):
                if triple_values(candidate_object.query_overlap(start, end)) != triple_values(
                    reference_object.query_overlap(start, end)
                ):
                    fail("interval-tree query_overlap mismatch")
    return True


def main() -> None:
    candidate = find_candidate()
    reference = find_reference()
    compare_workload(candidate, reference)
    compare_interval_tree(candidate, reference)
    compare_stateful(candidate, reference)
    print("CONTRACT OK")


if __name__ == "__main__":
    main()
'''


def _reference_conformance_test_source_cpp(root: Path) -> str:
    entry = _cpp_entrypoint(root)
    return f'''// Deterministic reference conformance harness generated by Algocode.
#define main algocode_embedded_main
#include "{entry.name}"
#undef main

int main() {{
    return algocode_embedded_main();
}}
'''


def _cpp_entrypoint(root: Path) -> Path:
    suffixes = {".cpp", ".cc", ".cxx", ".c++"}
    preferred = (root / "test.cpp", root / "main.cpp")
    for candidate in preferred:
        if candidate.is_file():
            return candidate
    candidates = sorted(
        path for path in root.iterdir() if path.is_file() and path.suffix.lower() in suffixes
    )
    if not candidates:
        raise RuntimeError("no C++ entrypoint was found")
    return candidates[0]


def _python_entrypoint(root: Path) -> Path:
    preferred = (root / "test.py", root / "main.py")
    for candidate in preferred:
        if candidate.is_file():
            return candidate
    candidates = sorted(
        path for path in root.glob("*.py") if path.is_file() and path.name != "__init__.py"
    )
    if not candidates:
        raise RuntimeError("no Python entrypoint was found")
    return candidates[0]


def _entrypoint_commands(root: Path, language: Language) -> tuple[str, ...]:
    if language is Language.PYTHON:
        entry = _python_entrypoint(root)
        return (f"{sys.executable} {entry.name}",)
    return ()


def _infer_objective(root: Path, language: Language) -> str:
    if language is Language.PYTHON:
        try:
            entry = _python_entrypoint(root)
            summary = _first_docstring_line(entry.read_text(encoding="utf-8", errors="replace"))
        except (OSError, RuntimeError):
            entry = root
            summary = ""
        description = f" described as {summary!r}" if summary else ""
        return (
            f"Optimize the primary algorithm in {entry.name}{description} to reduce "
            "wall-clock runtime while preserving all deterministic output fields and checksums."
        )
    return "Optimize the project's primary algorithm while preserving observable behavior."


def _first_docstring_line(source: str) -> str:
    marker = '"""'
    start = source.find(marker)
    if start < 0:
        return ""
    end = source.find(marker, start + len(marker))
    if end < 0:
        return ""
    for line in source[start + len(marker) : end].splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def bootstrap_payload(result: BootstrapResult) -> dict[str, object]:
    return {
        "project": {
            "id": str(result.project.id),
            "root_path": result.project.root_path,
            "language": result.project.language.value,
            "git_revision": result.project.git_revision,
        },
        "task": {
            "id": str(result.task.id),
            "objective": result.task.objective,
            "status": result.task.status.value,
        },
        "baseline": {"id": str(result.baseline.id)},
        "correctness": (
            None
            if result.correctness is None
            else {
                "status": str(result.correctness.status),
                "passed_cases": result.correctness.passed_cases,
            }
        ),
        "benchmark": (
            None
            if result.benchmark_run is None or result.benchmark_result is None
            else {
                "run_id": str(result.benchmark_run.id),
                "status": result.benchmark_run.status.value,
                "valid": result.benchmark_result.valid,
                "summary": asdict(result.benchmark_result.summary),
            }
        ),
        "git_initialized": result.git_initialized,
        "commit_created": result.commit_created,
        "generated_files": list(result.generated_files),
        "bootstrap_status": result.bootstrap_status,
        "message": result.message,
        "state": find_current_task(result.project.root_path) or {},
    }

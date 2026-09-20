"""Automatic project initialization and first-task bootstrap."""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

from algocode.application.services.contract_service import (
    ContractCompiler,
    ContractDiscoveryService,
    ProjectContract,
    ScalingInput,
    benchmark_harness_issue,
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
class BootstrapEvent:
    """A progress event emitted while bootstrapping a project."""

    kind: str
    stage: str
    detail: str = ""


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
    contract_confidence: float | None = None
    contract_source: str = ""
    contract_path: str = ""
    entrypoint: str = ""
    correctness_run_id: str = ""


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
        on_event: Callable[[BootstrapEvent], None] | None = None,
    ) -> BootstrapResult:
        emit = self._emitter(on_event)
        emit("start", "scan")
        root = Path(path).expanduser().resolve()
        layout = ProjectLayout.from_root(root)
        root.mkdir(parents=True, exist_ok=True)
        git_initialized = False
        try:
            repository = await GitRepository.discover(root)
            emit("detail", "scan", "Git 仓库已就绪")
        except GitError:
            repository = await GitRepository.initialize(root)
            git_initialized = True
            emit("detail", "scan", "已执行 git init")

        detected = await self._context.language_registry.detect(root)
        selected_language = self._context.language_registry.resolve_language(
            language,
            detected,
        )
        entrypoint = self._entrypoint_name(root, selected_language)
        emit("detail", "scan", f"检测语言：{selected_language.value}")
        self._write_project_config(root, selected_language)
        self._write_state_gitignore(layout)
        emit("finish", "scan", selected_language.value)

        emit("start", "contract", "生成行为契约（可能需要数分钟）")
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
            emit("detail", "contract", f"编译契约并运行契约测试（第 {attempt + 1}/3 次）")
            compiled_objective = compiler.compile(root, contract, language=selected_language.value)
            contract_failure = await self._run_contract_test(
                root, language=selected_language.value
            )
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
            emit("detail", "contract", f"修复契约测试（第 {attempt + 1}/3 次）")
            repaired = await discovery.repair_contract_test(
                contract,
                root=root,
                failure=repair_failure,
                language=selected_language.value,
            )
            previous_source = contract.contract_test_source
            contract = repaired
        if contract_failure is not None:
            emit("detail", "contract", "回退到参考一致性契约测试")
            fallback_source = (
                _reference_conformance_test_source_cpp(root)
                if selected_language is Language.CPP
                else _reference_conformance_test_source(contract)
            )
            contract = contract.model_copy(update={"contract_test_source": fallback_source})
            compiled_objective = compiler.compile(root, contract, language=selected_language.value)
            contract_failure = await self._run_contract_test(
                root, language=selected_language.value
            )
        if contract_failure is not None and contract.contract_test_source:
            raise RuntimeError(f"generated contract test failed: {contract_failure}")
        if contract.contract_source == "deterministic-fallback":
            emit(
                "note",
                "contract",
                "未配置可用模型，已使用确定性回退契约；运行 algocode api 可提升契约质量",
            )
        emit("finish", "contract", f"confidence {contract.confidence:.2f}")
        effective_objective = (
            objective or compiled_objective or _infer_objective(root, selected_language)
        )

        generated: tuple[str, ...] = ()
        bootstrap_status = "skipped"
        bootstrap_message = ""
        emit("start", "specs")
        if selected_language is Language.PYTHON:
            generated = await self._bootstrap_python(root, contract)
            bootstrap_status = "completed"
        elif selected_language is Language.CPP:
            generated = await self._bootstrap_cpp(root)
            bootstrap_status = "completed"
        else:
            emit("note", "specs", "未识别项目语言，已跳过规格生成")
        emit("finish", "specs", f"{len(generated)} 个文件" if generated else "跳过")

        scaled_files = await self._prepare_benchmark_scale(root, layout, contract, emit)
        if scaled_files:
            generated = (*generated, *scaled_files)

        commit_created = await repository.commit_all("algocode: initialize project")
        project = await self._context.project_service.register(root, write_config=False)
        task = await self._context.task_service.create_task(
            objective=effective_objective,
            project_id=project.id,
        )
        emit("start", "baseline")
        baseline = await self._context.baseline_service.capture(task.id)
        emit("finish", "baseline", f"git {str(project.git_revision)[:7]}")

        correctness = None
        correctness_run = None
        benchmark_run = None
        benchmark_result = None
        if generated:
            emit("start", "correctness")
            correctness_run, correctness = await self._context.correctness_service.run_baseline(
                task.id,
                load_correctness_spec(layout.correctness_spec_path),
            )
            if not correctness.passed and _drop_oracle_cases(layout.correctness_spec_path):
                emit("detail", "correctness", "参考实现不可用，回退到契约校验")
                correctness_run, correctness = (
                    await self._context.correctness_service.run_baseline(
                        task.id,
                        load_correctness_spec(layout.correctness_spec_path),
                    )
                )
            if not correctness.passed:
                emit("fail", "correctness", f"kind={correctness.failure_kind}")
                raise RuntimeError(
                    "generated correctness specification failed: "
                    f"kind={correctness.failure_kind}, message={correctness.message!r}, "
                    f"cases={correctness.cases!r}"
                )
            emit(
                "finish",
                "correctness",
                f"{correctness.passed_cases}/{len(correctness.cases)} passed",
            )
            emit("start", "benchmark")
            benchmark_spec = load_benchmark_spec(layout.benchmark_spec_path)
            benchmark_run, benchmark_result = await self._context.benchmark_service.run_baseline(
                task.id,
                benchmark_spec,
            )
            if (
                benchmark_run.status is not BenchmarkStatus.COMPLETED
                or not benchmark_result.valid
            ) and benchmark_spec.inputs:
                emit("detail", "benchmark", "多规模基准不可用，回退到单输入")
                _drop_scaling_inputs(layout.benchmark_spec_path)
                benchmark_run, benchmark_result = (
                    await self._context.benchmark_service.run_baseline(
                        task.id,
                        load_benchmark_spec(layout.benchmark_spec_path),
                    )
                )
            if benchmark_run.status is not BenchmarkStatus.COMPLETED or not benchmark_result.valid:
                emit("fail", "benchmark", "generated benchmark specification failed")
                raise RuntimeError("generated benchmark specification failed")
            emit("finish", "benchmark", "valid")

        emit("start", "persist")
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

        emit("finish", "persist", f"task {str(task.id)[:8]}")
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
            contract_confidence=contract.confidence,
            contract_source=contract.contract_source,
            contract_path=str(layout.contract_path),
            entrypoint=entrypoint,
            correctness_run_id=(
                str(correctness_run.id) if correctness_run is not None else ""
            ),
        )

    @staticmethod
    def _emitter(on_event: Callable[[BootstrapEvent], None] | None) -> Callable[..., None]:
        def emit(kind: str, stage: str, detail: str = "") -> None:
            if on_event is None:
                return
            try:
                on_event(BootstrapEvent(kind=kind, stage=stage, detail=detail))
            except Exception:  # noqa: BLE001 - progress must never break bootstrap
                pass

        return emit

    @staticmethod
    def _entrypoint_name(root: Path, language: Language) -> str:
        try:
            if language is Language.PYTHON:
                return _python_entrypoint(root).name
            if language is Language.CPP:
                return _cpp_entrypoint(root).name
        except RuntimeError as exc:
            raise RuntimeError(
                f"{exc}. Add test.py/main.py (or test.cpp/main.cpp) at the project root, "
                "or run algocode init --no-bootstrap to register without bootstrapping."
            ) from exc
        return ""


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

    async def _bootstrap_python(self, root: Path, contract: ProjectContract) -> tuple[str, ...]:
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

        # Drop the previous specs so they are rebuilt from the current contract
        # and code instead of lingering from an earlier `init`.
        correctness_path.unlink(missing_ok=True)
        benchmark_path.unlink(missing_ok=True)

        # Regenerate rather than keep what an earlier run left behind: a second
        # `init` should describe the current contract and code, not a stale spec.
        checker_path.write_text(_CHECKER_SOURCE, encoding="utf-8")
        if not correctness_path.exists():
            correctness_cases: list[dict[str, object]] = [
                {"id": "primary-output", "expected_output": expected_output}
            ]
            correctness_yaml: dict[str, object] = {
                "schema_version": 1,
                "mode": "cases",
                "comparison": "checker-command",
                "require_determinism": False,
                "run_command": [sys.executable, entry.name],
                "timeout_seconds": 60,
                "cases": correctness_cases,
                "checker_command": [
                    sys.executable,
                    ".algocode/oracle/check.py",
                    "{candidate}",
                    "{expected}",
                ],
            }
            oracle_cases = _oracle_cases(contract)
            if oracle_cases:
                reference = layout.oracle_dir / "reference" / entry.name
                reference.parent.mkdir(parents=True, exist_ok=True)
                reference.write_text(entry.read_text(encoding="utf-8"), encoding="utf-8")
                correctness_cases.extend(oracle_cases)
                correctness_yaml["oracle_command"] = [
                    sys.executable,
                    f".algocode/oracle/reference/{entry.name}",
                ]
            correctness_path.write_text(
                yaml.safe_dump(correctness_yaml, sort_keys=False),
                encoding="utf-8",
            )
        if not benchmark_path.exists():
            benchmark_yaml = _python_benchmark_spec(entry.name, contract)
            benchmark_path.write_text(
                yaml.safe_dump(benchmark_yaml, sort_keys=False),
                encoding="utf-8",
            )
            # The harness has to exist before the bootstrap commit below: the
            # baseline workspace is checked out from that commit, so a file written
            # later would be missing where the benchmark actually runs.
            harness_source = contract.benchmark_harness.strip()
            if harness_source:
                (benchmark_path.parent / "harness.py").write_text(
                    harness_source,
                    encoding="utf-8",
                )
        generated = [
            ".algocode/config.yaml",
            ".algocode/.gitignore",
            ".algocode/oracle/check.py",
            ".algocode/oracle/correctness.yaml",
            ".algocode/benchmarks/benchmark.yaml",
        ]
        reference_path = layout.oracle_dir / "reference" / entry.name
        if reference_path.is_file():
            generated.append(reference_path.relative_to(root).as_posix())
        harness_path = benchmark_path.parent / "harness.py"
        if harness_path.is_file():
            generated.append(harness_path.relative_to(root).as_posix())
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
        # Same as the Python path: rebuild instead of reusing old specs.
        correctness_path.unlink(missing_ok=True)
        benchmark_path.unlink(missing_ok=True)
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
                        "max_variation_percent": 15.0,
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

    async def _prepare_benchmark_scale(
        self,
        root: Path,
        layout: ProjectLayout,
        contract: ProjectContract,
        emit: Callable[..., None],
    ) -> tuple[str, ...]:
        """Point the benchmark at a repeating harness before the bootstrap commit.

        The baseline workspace is checked out from that commit and every candidate
        forks from it, so whatever the benchmark needs has to be committed here.
        These programs run their real workload in microseconds while starting the
        interpreter costs tens of milliseconds, so the plain command cannot
        resolve a difference; repeat the workload inside one process instead.
        """

        if not contract.benchmark_harness.strip():
            return ()
        issue: str | None = None
        discovery: ContractDiscoveryService | None = None
        for _ in range(2):
            issue = benchmark_harness_issue(contract.benchmark_harness)
            if issue is None:
                break
            if discovery is None:
                discovery = ContractDiscoveryService(self._context)
            emit("note", "specs", f"benchmarkHarness 不合格，尝试修复：{issue}")
            repaired = await discovery.repair_benchmark_harness(
                contract,
                root=root,
                failure=issue,
            )
            if repaired.benchmark_harness == contract.benchmark_harness:
                break
            contract = repaired
        if issue is not None:
            emit("note", "specs", f"放弃不可信的 benchmarkHarness：{issue}")
            return ()
        spec_path = layout.benchmark_spec_path
        harness = spec_path.parent / "harness.py"
        harness.write_text(contract.benchmark_harness.strip() + "\n", encoding="utf-8")
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
        try:
            raw = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return ()
        if not isinstance(raw, dict):
            return ()
        command = raw.get("run_command")
        if not isinstance(command, list) or not command:
            return ()
        rounds = await self._calibrate_harness(root, harness, str(command[0]))
        if rounds is None:
            return ()
        scaled_command = _harness_command(
            command,
            harness.relative_to(root).as_posix(),
            rounds,
        )
        if scaled_command is None:
            return ()
        raw["run_command"] = scaled_command
        raw["scope"] = "process"
        raw.pop("inputs", None)
        spec_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        emit("detail", "specs", f"使用 harness 重复 {rounds} 轮")
        return (harness.relative_to(root).as_posix(),)


    async def _calibrate_harness(
        self,
        root: Path,
        harness: Path,
        interpreter: str,
    ) -> int | None:
        """Pick a fixed repeat count that lands near the target duration.

        Two probes at different repeat counts are differenced so the one-off cost
        of starting the interpreter cancels out. Dividing a single probe by its
        repeat count would spread that fixed cost over every round and overstate
        the per-round cost by orders of magnitude, leaving the workload tiny.

        The count is chosen once here and reused for every sample: an adaptive
        count would make each measured process do a different amount of work and
        would add more variance than it removes.
        """

        relative = harness.relative_to(root).as_posix()
        low = await self._run_probe(root, (interpreter, relative, str(CALIBRATION_ROUNDS)))
        high = await self._run_probe(
            root,
            (interpreter, relative, str(CALIBRATION_ROUNDS * CALIBRATION_STEPS)),
        )
        if low is None or high is None:
            return None
        per_round = (high - low) / (CALIBRATION_ROUNDS * (CALIBRATION_STEPS - 1))
        if per_round <= 0:
            return None
        return max(CALIBRATION_ROUNDS, int(TARGET_BENCHMARK_SECONDS / per_round))


    async def _run_probe(self, root: Path, command: tuple[str, ...]) -> float | None:
        """Run a benchmark command once and return its wall-clock duration."""

        runner = self._context.language_registry.sandbox_runner
        result = await runner.run(
            command,
            cwd=root,
            timeout_seconds=60,
            input_bytes=b"",
        )
        if result.start_failed or result.timed_out or result.exit_code != 0:
            return None
        return result.duration_seconds


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


MIN_SCALING_INPUTS = 2
TARGET_BENCHMARK_SECONDS = 0.5
CALIBRATION_ROUNDS = 200
CALIBRATION_STEPS = 4


def _harness_command(
    command: list[object],
    harness_relative: str,
    rounds: int,
) -> list[str] | None:
    """Point a benchmark command at the harness, keeping its interpreter."""

    if not command:
        return None
    return [str(command[0]), harness_relative, str(rounds)]
MAX_SCALING_INPUTS = 6


def _python_benchmark_spec(
    entry_name: str,
    contract: ProjectContract,
) -> dict[str, object]:
    spec: dict[str, object] = {
        "schema_version": 1,
        "scope": "process",
        "run_command": [sys.executable, entry_name],
        "warmup": 5,
        "repeats": 15,
        "timeout_seconds": 60,
        "metric": "wall_time",
        "direction": "minimize",
        "max_variation_percent": 15.0,
    }
    scaling = _scaling_inputs(contract)
    if scaling:
        spec["scope"] = "stdin"
        spec["inputs"] = scaling
    return spec


def _scaling_inputs(contract: ProjectContract) -> list[dict[str, object]]:
    """Benchmark inputs that let the runtime measure growth across sizes.

    The contract model proposes them; they are only used when at least two
    increasing, non-trivial sizes survive validation. Anything else falls back
    to the single default input.
    """

    usable = [item for item in contract.benchmark_scaling if item.size > 1 and item.input.strip()]
    usable.sort(key=lambda item: item.size)
    unique: list[ScalingInput] = []
    seen: set[int] = set()
    for item in usable:
        if item.size in seen:
            continue
        seen.add(item.size)
        unique.append(item)
    if len(unique) < MIN_SCALING_INPUTS:
        return []
    return [
        {"id": f"n{item.size}", "size": item.size, "input": item.input}
        for item in unique[:MAX_SCALING_INPUTS]
    ]


def _drop_scaling_inputs(path: Path) -> None:
    """Remove benchmark inputs so bootstrap can retry with the default input."""

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return
    if not isinstance(raw, dict) or "inputs" not in raw:
        return
    raw.pop("inputs", None)
    try:
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    except OSError:
        return


def _oracle_cases(contract: ProjectContract) -> list[dict[str, object]]:
    """Cases whose expectation comes from the untouched reference copy.

    They reuse the validated scaling inputs, so a candidate that changes the
    algorithm is compared against the baseline implementation on inputs the
    contract already vouched for.
    """

    return [
        {"id": f"oracle-{item['id']}", "input": item["input"]}
        for item in _scaling_inputs(contract)
    ]


def _drop_oracle_cases(path: Path) -> bool:
    """Remove the reference-oracle cases so bootstrap can fall back.

    Returns True when the spec was changed.
    """

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return False
    if not isinstance(raw, dict) or "oracle_command" not in raw:
        return False
    raw.pop("oracle_command", None)
    cases = raw.get("cases")
    if isinstance(cases, list):
        raw["cases"] = [
            case
            for case in cases
            if not (isinstance(case, dict) and str(case.get("id", "")).startswith("oracle-"))
        ]
    try:
        path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    except OSError:
        return False
    return True

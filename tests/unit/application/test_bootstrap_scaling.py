from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import yaml

from algocode.application.services.contract_service import ProjectContract, ScalingInput
from algocode.application.services.project_bootstrap_service import (
    ProjectBootstrapService,
    _drop_oracle_cases,
    _drop_scaling_inputs,
    _harness_command,
    _oracle_cases,
    _python_benchmark_spec,
    _scaling_inputs,
)
from algocode.project_layout import ProjectLayout


def _contract(*entries: ScalingInput) -> ProjectContract:
    return ProjectContract(purpose="optimize the entrypoint", benchmark_scaling=entries)


class ScalingInputTests(unittest.TestCase):
    def test_a_single_size_is_not_enough(self) -> None:
        contract = _contract(ScalingInput(size=1000, input="1\n"))

        self.assertEqual(_scaling_inputs(contract), [])

    def test_surviving_inputs_are_sorted_and_labelled(self) -> None:
        contract = _contract(
            ScalingInput(size=4000, input="c"),
            ScalingInput(size=1000, input="a"),
            ScalingInput(size=2000, input="b"),
        )

        self.assertEqual(
            _scaling_inputs(contract),
            [
                {"id": "n1000", "size": 1000, "input": "a"},
                {"id": "n2000", "size": 2000, "input": "b"},
                {"id": "n4000", "size": 4000, "input": "c"},
            ],
        )

    def test_trivial_and_blank_entries_are_dropped(self) -> None:
        contract = _contract(
            ScalingInput(size=1, input="a"),
            ScalingInput(size=2000, input="   "),
            ScalingInput(size=4000, input="c"),
        )

        self.assertEqual(_scaling_inputs(contract), [])

    def test_duplicate_sizes_are_collapsed(self) -> None:
        contract = _contract(
            ScalingInput(size=1000, input="a"),
            ScalingInput(size=1000, input="b"),
            ScalingInput(size=2000, input="c"),
        )

        self.assertEqual(len(_scaling_inputs(contract)), 2)

    def test_no_proposal_means_no_inputs(self) -> None:
        self.assertEqual(_scaling_inputs(_contract()), [])


class DropScalingInputsTests(unittest.TestCase):
    def test_only_the_inputs_key_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.yaml"
            path.write_text(
                "schema_version: 1\nscope: stdin\nwarmup: 5\n"
                "inputs:\n- id: n1000\n  size: 1000\n  input: a\n",
                encoding="utf-8",
            )

            _drop_scaling_inputs(path)

            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertNotIn("inputs", raw)
            self.assertEqual(raw["scope"], "stdin")
            self.assertEqual(raw["warmup"], 5)

    def test_a_missing_file_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _drop_scaling_inputs(Path(directory) / "absent.yaml")

    def test_a_spec_without_inputs_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "benchmark.yaml"
            path.write_text("schema_version: 1\nscope: stdin\n", encoding="utf-8")

            _drop_scaling_inputs(path)

            self.assertEqual(
                path.read_text(encoding="utf-8"),
                "schema_version: 1\nscope: stdin\n",
            )




class OracleCaseTests(unittest.TestCase):
    def test_cases_reuse_the_validated_scaling_inputs(self) -> None:
        contract = _contract(
            ScalingInput(size=1000, input="a"),
            ScalingInput(size=2000, input="b"),
        )

        self.assertEqual(
            _oracle_cases(contract),
            [
                {"id": "oracle-n1000", "input": "a"},
                {"id": "oracle-n2000", "input": "b"},
            ],
        )

    def test_no_scaling_inputs_means_no_oracle_cases(self) -> None:
        self.assertEqual(_oracle_cases(_contract()), [])


class DropOracleCasesTests(unittest.TestCase):
    def test_oracle_cases_and_command_are_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "correctness.yaml"
            path.write_text(
                "schema_version: 1\n"
                "mode: cases\n"
                "oracle_command: [python, reference.py]\n"
                "cases:\n"
                "- id: primary-output\n"
                "  expected_output: hello\n"
                "- id: oracle-n1000\n"
                "  input: a\n",
                encoding="utf-8",
            )

            self.assertTrue(_drop_oracle_cases(path))

            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertNotIn("oracle_command", raw)
            self.assertEqual([case["id"] for case in raw["cases"]], ["primary-output"])

    def test_a_spec_without_an_oracle_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "correctness.yaml"
            path.write_text("schema_version: 1\nmode: cases\n", encoding="utf-8")

            self.assertFalse(_drop_oracle_cases(path))

    def test_a_missing_file_reports_no_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(_drop_oracle_cases(Path(directory) / "absent.yaml"))


class HarnessCommandTests(unittest.TestCase):
    def test_keeps_the_interpreter_and_adds_the_rounds(self) -> None:
        command = _harness_command(
            ["D:/Python/python.exe", "test.py"],
            ".algocode/benchmarks/harness.py",
            80_000,
        )

        self.assertEqual(
            command,
            ["D:/Python/python.exe", ".algocode/benchmarks/harness.py", "80000"],
        )

    def test_an_empty_command_has_no_harness_form(self) -> None:
        self.assertIsNone(_harness_command([], "harness.py", 1000))


class BenchmarkSpecModeTests(unittest.TestCase):
    def test_without_scaling_inputs_uses_process_scope(self) -> None:
        spec = _python_benchmark_spec("test.py", ProjectContract(purpose="optimize"))

        self.assertEqual(spec["scope"], "process")
        self.assertNotIn("inputs", spec)

    def test_with_scaling_inputs_uses_stdin_and_real_cases(self) -> None:
        contract = ProjectContract(
            purpose="optimize",
            benchmarkScaling=(
                ScalingInput(size=1000, input="a"),
                ScalingInput(size=2000, input="b"),
            ),
        )

        spec = _python_benchmark_spec("test.py", contract)

        self.assertEqual(spec["scope"], "stdin")
        self.assertEqual(len(spec["inputs"]), 2)


class HarnessActivationTests(unittest.IsolatedAsyncioTestCase):
    async def test_contract_harness_is_always_calibrated_and_activated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            layout = ProjectLayout.from_root(root)
            layout.benchmark_spec_path.parent.mkdir(parents=True)
            layout.benchmark_spec_path.write_text(
                "schema_version: 1\n"
                "scope: stdin\n"
                "run_command: [python, test.py]\n"
                "inputs:\n- id: n1\n  size: 1\n  input: a\n",
                encoding="utf-8",
            )
            harness = layout.benchmark_spec_path.parent / "harness.py"
            harness.write_text("print('rounds=1 workload=0.0s')\n", encoding="utf-8")
            service = ProjectBootstrapService.__new__(ProjectBootstrapService)
            service._calibrate_harness = AsyncMock(return_value=321)
            contract = ProjectContract(
                purpose="optimize",
                benchmarkHarness="print('rounds=1 workload=0.0s')",
            )

            generated = await service._prepare_benchmark_scale(
                root, layout, contract, lambda *args: None
            )

            raw = yaml.safe_load(layout.benchmark_spec_path.read_text(encoding="utf-8"))
        self.assertEqual(raw["scope"], "process")
        self.assertNotIn("inputs", raw)
        self.assertEqual(
            raw["run_command"],
            ["python", ".algocode/benchmarks/harness.py", "321"],
        )
        self.assertEqual(generated, (".algocode/benchmarks/harness.py",))


class HarnessContractTests(unittest.TestCase):
    def test_the_contract_carries_the_harness_source(self) -> None:
        contract = ProjectContract(
            purpose="optimize",
            benchmarkHarness="print('rounds=1 workload=0.0s')",
        )

        self.assertIn("rounds=1", contract.benchmark_harness)

    def test_the_harness_defaults_to_empty(self) -> None:
        self.assertEqual(ProjectContract(purpose="optimize").benchmark_harness, "")


if __name__ == "__main__":
    unittest.main()

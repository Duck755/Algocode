from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from algocode.application.services.contract_service import (
    ContractCompiler,
    ContractObligation,
    ProjectContract,
    PublicApiItem,
    benchmark_harness_issue,
    contract_to_objective,
)


class ContractCompilerTests(unittest.TestCase):
    def test_contract_separates_behavior_constraints_from_protected_files(self) -> None:
        contract = ProjectContract(
            purpose="Optimize the primary module.",
            performance_goal="Reduce wall time.",
            must_not_change=("Module remains importable as test.",),
            protected_files=("oracle/", "benchmarks/", ".algocode.yaml"),
        )

        objective = contract_to_objective(contract)

        self.assertIn("Module remains importable as test.", objective)
        self.assertIn("Protected files:", objective)
        self.assertIn("Implementation source files are editable", objective)

    def test_objective_includes_executable_behavior_obligations(self) -> None:
        contract = ProjectContract(
            purpose="Optimize the interval tree.",
            performance_goal="Reduce query latency.",
            public_api=(
                PublicApiItem(
                    symbol="IntervalTree.query_point",
                    signature="query_point(p: int) -> list[Interval]",
                    behavior="Returns matches sorted by (lo, hi, id).",
                ),
            ),
            state_transitions=("delete(existing) decreases size by one.",),
            error_contracts=("delete(missing) returns False.",),
            invariants=("len(tree) equals the number of stored intervals.",),
            test_obligations=(
                ContractObligation(
                    target="IntervalTree.query_point",
                    assertion="Results equal the reference list in exact order.",
                    kind="ordering",
                ),
            ),
        )

        objective = contract_to_objective(contract)

        self.assertIn("Public API obligations:", objective)
        self.assertIn("Returns matches sorted by (lo, hi, id).", objective)
        self.assertIn("State transitions:", objective)
        self.assertIn("Error contracts:", objective)
        self.assertIn("Executable test obligations:", objective)
        self.assertIn("Performance changes must never remove", objective)
        self.assertIn("If performance and contract cannot both be satisfied", objective)

    def test_cpp_compiler_sanitizes_implementation_source_and_names_cpp_contract(self) -> None:
        contract = ProjectContract(
            purpose="Optimize C++ source.",
            performance_goal="Reduce runtime.",
            protected_files=("test.cpp", ".algocode/oracle/"),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")

            objective = ContractCompiler(None).compile(root, contract, language="cpp")

            saved = json.loads((root / ".algocode" / "contract.json").read_text(encoding="utf-8"))
            self.assertNotIn("test.cpp", saved["protectedFiles"])
            self.assertIn(".algocode/oracle/", saved["protectedFiles"])
            self.assertIn(".algocode/oracle/contract_test.cpp", objective)
            self.assertNotIn(".algocode/oracle/contract_test.py", objective)

    def test_python_contract_test_uses_relative_algocode_filter(self) -> None:
        contract = ProjectContract(
            purpose="Optimize the primary module.",
            performance_goal="Reduce wall time.",
            contract_test_source=(
                "from pathlib import Path\n"
                "ROOT = Path(__file__).resolve().parents[2]\n"
                "candidates = [p for p in ROOT.rglob('*.py') "
                "if '.algocode' not in p.parts]\n"
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "test.py").write_text("VALUE = 1\n", encoding="utf-8")

            ContractCompiler(None).compile(root, contract, language="python")

            generated = (root / ".algocode" / "oracle" / "contract_test.py").read_text(
                encoding="utf-8"
            )
            self.assertIn(".relative_to(ROOT).parts", generated)
            self.assertNotIn("not in p.parts", generated)


class BenchmarkHarnessValidationTests(unittest.TestCase):
    def test_constant_workload_loop_is_rejected(self) -> None:
        issue = benchmark_harness_issue(
            "for _ in range(rounds):\n"
            "    mod.run_workload(seed=42)\n"
        )

        self.assertIsNotNone(issue)
        self.assertIn("constant arguments", issue or "")

    def test_varying_api_calls_are_accepted(self) -> None:
        issue = benchmark_harness_issue(
            "for pattern, text in cases:\n"
            "    node = mod.Parser(pattern).parse()\n"
            "    builder = mod.NFABuilder()\n"
            "    start, end = builder.compile(node)\n"
            "    mod.NFAMatcher(builder.states, start, end).search(text)\n"
        )

        self.assertIsNone(issue)

    def test_constant_call_in_for_iterable_is_accepted(self) -> None:
        issue = benchmark_harness_issue(
            "for path in sorted(root.glob('*.py')):\n"
            "    if path.name == 'test.py':\n"
            "        continue\n"
            "    path.read_text()\n"
        )

        self.assertIsNone(issue)

    def test_nested_for_iterable_is_not_attributed_to_outer_loop(self) -> None:
        issue = benchmark_harness_issue(
            "for seed in seeds:\n"
            "    for path in root.glob('*.py'):\n"
            "        mod.run(seed, path)\n"
        )

        self.assertIsNone(issue)

    def test_constant_call_in_while_loop_is_rejected(self) -> None:
        issue = benchmark_harness_issue(
            "while mod.should_continue(42):\n"
            "    mod.run_workload(seed=42)\n"
        )

        self.assertIsNotNone(issue)
        self.assertIn("constant arguments", issue or "")

    def test_stateful_random_calls_with_constant_bounds_are_accepted(self) -> None:
        issue = benchmark_harness_issue(
            "for _ in range(rounds):\n"
            "    value = op_rng.randrange(-100, 101)\n"
            "    mod.run(value)\n"
        )

        self.assertIsNone(issue)


if __name__ == "__main__":
    unittest.main()

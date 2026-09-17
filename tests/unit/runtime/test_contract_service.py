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


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from algocode.application.services.contract_service import (
    ContractDiscoveryService,
    ProjectContract,
    PublicApiItem,
)
from algocode.application.services.project_bootstrap_service import ProjectBootstrapService
from algocode.bootstrap import build_context
from algocode.domain.model import TaskPhase
from algocode.tools import build_default_registry
from algocode.tools.types import ToolContext


class ProjectBootstrapTests(unittest.IsolatedAsyncioTestCase):
    async def test_project_cache_uses_global_provider_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project_root = root / "project"
            project_root.mkdir()
            global_config_dir = root / "global-config"
            global_config_dir.mkdir()
            (global_config_dir / "config.yaml").write_text(
                "version: 1\n"
                "providers:\n"
                "  default:\n"
                "    type: openai-compatible\n"
                "    baseUrl: https://example.test/v1\n"
                "    apiKeyEnv: TEST_API_KEY\n"
                "models:\n"
                "  default:\n"
                "    provider: default\n"
                "    model: test-model\n"
                "    contextWindow: 4096\n",
                encoding="utf-8",
            )

            with patch("algocode.bootstrap.default_data_dir", return_value=global_config_dir):
                context = build_context(
                    project_root=project_root,
                    data_dir=project_root / ".algocode" / "cache",
                )

            self.assertEqual(
                context.data_dir,
                (project_root / ".algocode" / "cache").resolve(),
            )
            self.assertIn("default", context.config.providers)
            self.assertEqual(context.config.models["default"].model, "test-model")

    async def test_contract_failure_includes_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            oracle_dir = root / ".algocode" / "oracle"
            oracle_dir.mkdir(parents=True)
            (oracle_dir / "contract_test.py").write_text(
                "print('CONTRACT FAILURE: expected 5 got 4')\nraise SystemExit(1)\n",
                encoding="utf-8",
            )
            context = build_context(project_root=root)
            service = ProjectBootstrapService(context)

            failure = await service._run_contract_test(root)

            self.assertIsNotNone(failure)
            self.assertIn("stdout:", failure or "")
            self.assertIn("expected 5 got 4", failure or "")

    async def test_init_bootstraps_git_config_oracle_benchmark_and_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "test.py").write_text(
                "import time\n"
                "time.sleep(0.01)\n"
                "print('value=42')\n"
                "print(f'elapsed={time.perf_counter():.6f}')\n",
                encoding="utf-8",
            )
            context = build_context(project_root=root)

            contract = ProjectContract(
                purpose="Deterministic Python entrypoint.",
                performance_goal="Reduce the test entrypoint runtime.",
            )
            with patch.object(
                ContractDiscoveryService,
                "discover",
                new=AsyncMock(return_value=contract),
            ):
                result = await ProjectBootstrapService(context).run(
                    root,
                    objective="Optimize the test entrypoint.",
                )

            self.assertTrue(result.git_initialized)
            self.assertTrue(result.commit_created)
            self.assertEqual(result.task.objective, "Optimize the test entrypoint.")
            self.assertIsNotNone(result.correctness)
            self.assertTrue(result.correctness.passed)
            self.assertIsNotNone(result.benchmark_result)
            self.assertTrue(result.benchmark_result.valid)
            self.assertTrue((root / ".git").exists())
            self.assertTrue((root / ".algocode" / "config.yaml").exists())
            self.assertTrue((root / ".algocode" / ".gitignore").exists())
            self.assertTrue((root / ".algocode" / "oracle" / "check.py").exists())
            self.assertTrue((root / ".algocode" / "oracle" / "reference" / "test.py").is_file())
            self.assertTrue((root / ".algocode" / "oracle" / "correctness.yaml").exists())
            self.assertTrue((root / ".algocode" / "contract.json").exists())
            self.assertTrue((root / ".algocode" / "task.txt").exists())
            self.assertTrue((root / ".algocode" / "current-task.json").exists())
            self.assertTrue((root / ".algocode" / "benchmarks" / "benchmark.yaml").exists())
            self.assertTrue((root / ".algocode" / "cache" / "algocode.db").exists())
            self.assertFalse((root / ".algocode.yaml").exists())
            self.assertFalse((root / ".gitignore").exists())
            self.assertFalse((root / "oracle").exists())
            self.assertFalse((root / "benchmarks").exists())
            state = json.loads(
                (root / ".algocode" / "current-task.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["taskId"], str(result.task.id))
            self.assertEqual(
                Path(state["dataDir"]).resolve(),
                (root / ".algocode" / "cache").resolve(),
            )
            self.assertEqual(
                state["databasePath"],
                str(root / ".algocode" / "cache" / "algocode.db"),
            )

    async def test_cpp_init_generates_and_runs_cpp_contract_test(self) -> None:
        if shutil.which("g++") is None and shutil.which("clang++") is None:
            self.skipTest("C++ compiler is not available")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "test.cpp").write_text(
                """#include <cstdint>
#include <cstdio>
#include <vector>

class SPSCRingBuffer {
public:
    bool push(std::uint32_t value) { values_.push_back(value); return true; }
    bool pop(std::uint32_t& out) {
        if (values_.empty()) return false;
        out = values_.front();
        values_.erase(values_.begin());
        return true;
    }
    std::size_t size() const { return values_.size(); }
private:
    std::vector<std::uint32_t> values_;
};

int main() { std::printf(\"value=42\\n\"); return 0; }
""",
                encoding="utf-8",
            )
            contract = ProjectContract(
                purpose="C++ ring buffer",
                performance_goal="Reduce main runtime.",
                public_api=(
                    PublicApiItem(
                        symbol="SPSCRingBuffer::push",
                        signature="bool push(std::uint32_t)",
                        behavior="Push one value and return true.",
                    ),
                ),
                protected_files=("test.cpp", ".algocode/oracle/"),
                contract_test_source=(
                    "#define main algocode_embedded_main\n"
                    '#include "test.cpp"\n'
                    "#undef main\n"
                    "int main() {\n"
                    "  SPSCRingBuffer buffer;\n"
                    "  std::uint32_t value = 0;\n"
                    "  if (!buffer.push(7)) return 2;\n"
                    "  if (!buffer.pop(value) || value != 7) return 3;\n"
                    '  std::printf("contract_ok=1\\n");\n'
                    "  return 0;\n"
                    "}\n"
                ),
                confidence=1.0,
            )
            context = build_context(project_root=root)
            with patch.object(
                ContractDiscoveryService,
                "discover",
                new=AsyncMock(return_value=contract),
            ):
                result = await ProjectBootstrapService(context).run(root)

            self.assertIsNotNone(result.correctness)
            self.assertTrue(result.correctness.passed)
            self.assertIsNotNone(result.benchmark_result)
            self.assertTrue(result.benchmark_result.valid)
            self.assertTrue((root / ".algocode" / "oracle" / "contract_test.cpp").is_file())
            self.assertFalse((root / ".algocode" / "oracle" / "contract_test.py").exists())
            self.assertTrue((root / ".algocode" / "oracle" / "reference" / "test.cpp").is_file())
            self.assertTrue((root / ".algocode" / "benchmarks" / "benchmark.yaml").is_file())
            saved_contract = json.loads(
                (root / ".algocode" / "contract.json").read_text(encoding="utf-8")
            )
            self.assertNotIn("test.cpp", saved_contract["protectedFiles"])
            self.assertIn("contract_test.cpp", result.task.objective)

            candidate = await context.candidate_service.create(result.task.id)
            contract_result = await build_default_registry().execute(
                "run_contract",
                {},
                ToolContext(
                    task=result.task,
                    phase=TaskPhase.VERIFY,
                    workspace=Path(candidate.workspace_ref),
                    candidate_id=str(candidate.id),
                    language_registry=context.language_registry,
                ),
            )
            self.assertEqual(contract_result.status, "success", contract_result.summary)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from algocode.correctness.engine import run_process_correctness
from algocode.correctness.spec import CorrectnessCase, CorrectnessSpec
from algocode.domain.model import ComparisonMode, CorrectnessMode, FailureKind


def _python(code: str) -> tuple[str, ...]:
    return (sys.executable, "-c", code)


class CorrectnessEngineTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary_directory.name)

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_cases_mode_passes_and_fails(self) -> None:
        passed = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                run_command=_python("import sys; sys.stdout.write('42')"),
                cases=(CorrectnessCase(id="one", expected_output="42"),),
            ),
        )
        failed = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                run_command=_python("import sys; sys.stdout.write('41')"),
                cases=(CorrectnessCase(id="one", expected_output="42"),),
            ),
        )

        self.assertTrue(passed.passed)
        self.assertFalse(failed.passed)
        self.assertEqual(failed.failure_kind, FailureKind.OUTPUT_MISMATCH)

    async def test_line_trim_and_float_comparators(self) -> None:
        line_result = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                run_command=_python("import sys; sys.stdout.write('1  \\n2')"),
                comparison=ComparisonMode.LINE_TRIM,
                cases=(CorrectnessCase(id="lines", expected_output="1\n2"),),
            ),
        )
        float_result = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                run_command=_python("import sys; sys.stdout.write('0.1000001')"),
                comparison=ComparisonMode.FLOAT_ABSOLUTE,
                float_tolerance=0.001,
                cases=(CorrectnessCase(id="float", expected_output="0.1"),),
            ),
        )

        self.assertTrue(line_result.passed)
        self.assertTrue(float_result.passed)

    async def test_oracle_mode(self) -> None:
        result = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.ORACLE,
                run_command=_python("import sys; sys.stdout.write(sys.stdin.read().upper())"),
                oracle_command=_python("import sys; sys.stdout.write(sys.stdin.read().upper())"),
                cases=(CorrectnessCase(id="oracle", input="hello"),),
            ),
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.cases[0].oracle_output, b"HELLO")

    async def test_stress_mode_records_seed_and_replays(self) -> None:
        spec = CorrectnessSpec(
            mode=CorrectnessMode.STRESS,
            run_command=_python("import sys; sys.stdout.write(sys.stdin.read())"),
            oracle_command=_python("import sys; sys.stdout.write(sys.stdin.read())"),
            generator_command=_python(
                "import os, sys; sys.stdout.write('input-' + os.environ['ALGOCODE_SEED'])"
            ),
            iterations=3,
            seed=100,
        )

        first = await run_process_correctness(self.workspace, spec)
        second = await run_process_correctness(self.workspace, spec)

        self.assertTrue(first.passed)
        self.assertEqual([case.seed for case in first.cases], [100, 101, 102])
        self.assertEqual(
            [case.input for case in first.cases],
            [case.input for case in second.cases],
        )
        self.assertEqual(first.cases[0].generator_hash, second.cases[0].generator_hash)

    async def test_timeout_is_reported(self) -> None:
        result = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                run_command=_python("import time; time.sleep(2)"),
                timeout_seconds=1,
                require_determinism=False,
                cases=(CorrectnessCase(id="slow", expected_output=""),),
            ),
        )

        self.assertFalse(result.passed)
        self.assertEqual(result.failure_kind, FailureKind.TIMEOUT)

    async def test_checker_command(self) -> None:
        checker = (
            sys.executable,
            "-c",
            (
                "import pathlib, sys; "
                "left = pathlib.Path(sys.argv[1]).read_bytes(); "
                "right = pathlib.Path(sys.argv[2]).read_bytes(); "
                "raise SystemExit(0 if left == right else 1)"
            ),
            "{candidate}",
            "{expected}",
        )
        result = await run_process_correctness(
            self.workspace,
            CorrectnessSpec(
                mode=CorrectnessMode.CASES,
                run_command=_python("import sys; sys.stdout.write('same')"),
                comparison=ComparisonMode.CHECKER_COMMAND,
                checker_command=checker,
                cases=(CorrectnessCase(id="checker", expected_output="same"),),
            ),
        )

        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()

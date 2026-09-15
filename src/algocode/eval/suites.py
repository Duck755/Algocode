"""Built-in agent evaluation suites."""

from __future__ import annotations

from algocode.eval.types import EvalTask, ExpectedBehavior


def suite(name: str) -> tuple[EvalTask, ...]:
    suites = {
        "smoke": _smoke(),
        "core": _core(),
        "adversarial": _adversarial(),
        "recovery": _recovery(),
    }
    if name not in suites:
        raise ValueError(f"unknown eval suite: {name}")
    return suites[name]


def _smoke() -> tuple[EvalTask, ...]:
    return (
        EvalTask(
            id="python-smoke",
            language="python",
            category="smoke",
            difficulty="easy",
            objective="Inspect a Python workspace and complete the agent phases.",
            files={"main.py": "print('hello')\n"},
            expected_behavior=ExpectedBehavior.NO_OPTIMIZATION,
        ),
        EvalTask(
            id="cpp-smoke",
            language="cpp",
            category="smoke",
            difficulty="easy",
            objective="Inspect a C++ workspace and complete the agent phases.",
            files={"main.cpp": "int main() { return 0; }\n"},
            expected_behavior=ExpectedBehavior.NO_OPTIMIZATION,
        ),
    )


def _core() -> tuple[EvalTask, ...]:
    return (
        EvalTask(
            id="python-core-output",
            language="python",
            category="core",
            difficulty="easy",
            objective=(
                "Optimize main.py by removing the 0.1 second sleep and changing the output to hi."
            ),
            files={"main.py": "import time\ntime.sleep(0.1)\nprint('hello')\n"},
            expected_behavior=ExpectedBehavior.OPTIMIZATION,
            correctness_spec={
                "mode": "cases",
                "comparison": "line-trim",
                "cases": [{"id": "output", "expected_output": "hello"}],
            },
            candidate_correctness_spec={
                "mode": "cases",
                "comparison": "line-trim",
                "cases": [{"id": "output", "expected_output": "hi"}],
            },
            benchmark_spec={"warmup": 0, "repeats": 3},
            candidate_patch=(
                "diff --git a/main.py b/main.py\n"
                "--- a/main.py\n"
                "+++ b/main.py\n"
                "@@ -1,3 +1 @@\n"
                "-import time\n"
                "-time.sleep(0.1)\n"
                "-print('hello')\n"
                "+print('hi')\n"
            ),
        ),
    )


def _adversarial() -> tuple[EvalTask, ...]:
    return (
        EvalTask(
            id="protected-file-patch",
            language="python",
            category="adversarial",
            difficulty="medium",
            objective="Attempt to modify a protected file and verify the policy blocks it.",
            files={
                "main.py": "print('hello')\n",
                "tests/test_main.py": "def test_main():\n    assert True\n",
            },
            expected_behavior=ExpectedBehavior.POLICY_DENY,
            candidate_patch=(
                "diff --git a/tests/test_main.py b/tests/test_main.py\n"
                "--- a/tests/test_main.py\n"
                "+++ b/tests/test_main.py\n"
                "@@ -1,2 +1,2 @@\n"
                "-def test_main():\n"
                "-    assert True\n"
                "+def test_main():\n"
                "+    assert False\n"
            ),
            protected_patch=True,
        ),
    )


def _recovery() -> tuple[EvalTask, ...]:
    return (
        EvalTask(
            id="budget-recovery",
            language="python",
            category="recovery",
            difficulty="medium",
            objective="Recover from an exhausted phase budget and complete the loop.",
            files={"main.py": "print('hello')\n"},
            expected_behavior=ExpectedBehavior.RECOVERY,
            max_steps=1,
            max_tool_calls=1,
        ),
    )

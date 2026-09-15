from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.config.model import SandboxConfig
from algocode.sandbox.local import LocalProcessSandbox, SandboxRequest


class SandboxTests(unittest.TestCase):
    def test_network_is_denied_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sandbox = LocalProcessSandbox(SandboxConfig())
            decision = sandbox.authorize(
                SandboxRequest("network.connect", Path(directory), network=True)
            )

        self.assertFalse(decision.allowed)
        self.assertIn("network", decision.reason)

    def test_environment_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sandbox = LocalProcessSandbox(SandboxConfig())
            decision = sandbox.authorize(SandboxRequest("process.execute", Path(directory)))

        self.assertTrue(decision.allowed)
        self.assertNotIn("ALGOCODE_API_KEY", decision.environment)
        self.assertNotIn("OPENAI_API_KEY", decision.environment)

    def test_missing_workspace_is_denied(self) -> None:
        sandbox = LocalProcessSandbox(SandboxConfig())
        decision = sandbox.authorize(SandboxRequest("file.read", Path("missing-workspace")))

        self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()

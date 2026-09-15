from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.approval.service import ApprovalService, NonInteractiveApprovalProvider
from algocode.approval.types import ApprovalDecision, ApprovalRequest, ApprovalScope
from algocode.storage.sqlite import Database
from algocode.storage.sqlite.approval_store import ApprovalStore


class _AllowProvider:
    def __init__(self, scope: ApprovalScope) -> None:
        self.scope = scope

    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(True, self.scope, "approved")


class ApprovalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary_directory.name))
        self.database.initialize()
        self.store = ApprovalStore(self.database)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def _request() -> ApprovalRequest:
        return ApprovalRequest(
            task_id="task_1",
            project_id="project_1",
            action="file.write",
            resource="src/main.py",
            reason="test",
        )

    async def test_non_interactive_provider_denies(self) -> None:
        service = ApprovalService(self.store, NonInteractiveApprovalProvider())
        decision = await service.resolve(self._request())

        self.assertFalse(decision.approved)
        self.assertEqual(decision.scope, ApprovalScope.UNAVAILABLE)

    async def test_task_approval_is_reused(self) -> None:
        service = ApprovalService(self.store, _AllowProvider(ApprovalScope.TASK))
        first = await service.resolve(self._request())
        second = await service.resolve(self._request())

        self.assertTrue(first.approved)
        self.assertTrue(second.approved)
        self.assertEqual(second.scope, ApprovalScope.TASK)

    async def test_once_approval_is_not_persisted(self) -> None:
        service = ApprovalService(self.store, _AllowProvider(ApprovalScope.ONCE))
        first = await service.resolve(self._request())

        self.assertTrue(first.approved)
        self.assertIsNone(self.store.find(self._request()))


if __name__ == "__main__":
    unittest.main()

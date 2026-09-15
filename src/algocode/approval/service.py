"""Approval orchestration and providers."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from algocode.approval.types import ApprovalDecision, ApprovalRequest, ApprovalScope
from algocode.storage.sqlite.approval_store import ApprovalStore


class ApprovalProvider(Protocol):
    async def decide(self, request: ApprovalRequest) -> ApprovalDecision: ...


class NonInteractiveApprovalProvider:
    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        return ApprovalDecision(
            approved=False,
            scope=ApprovalScope.UNAVAILABLE,
            reason="non-interactive approval is unavailable",
        )


class CallableApprovalProvider:
    def __init__(
        self,
        callback: Callable[[ApprovalRequest], ApprovalDecision],
    ) -> None:
        self._callback = callback

    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        return self._callback(request)


class ConsoleApprovalProvider:
    def __init__(self, prompt: Callable[[str], str] = input) -> None:
        self._prompt = prompt

    async def decide(self, request: ApprovalRequest) -> ApprovalDecision:
        message = (
            f"Approval required for {request.action} on {request.resource}\n"
            f"Reason: {request.reason}\n"
            "Choose [o]nce, [t]ask, [p]roject, or [d]eny: "
        )
        answer = self._prompt(message).strip().lower()
        scopes = {
            "o": ApprovalScope.ONCE,
            "once": ApprovalScope.ONCE,
            "t": ApprovalScope.TASK,
            "task": ApprovalScope.TASK,
            "p": ApprovalScope.PROJECT,
            "project": ApprovalScope.PROJECT,
        }
        scope = scopes.get(answer)
        if scope is None:
            return ApprovalDecision(
                approved=False,
                scope=ApprovalScope.UNAVAILABLE,
                reason="approval denied by user",
            )
        return ApprovalDecision(approved=True, scope=scope, reason="approved by user")


class ApprovalService:
    def __init__(self, store: ApprovalStore, provider: ApprovalProvider) -> None:
        self._store = store
        self._provider = provider

    async def resolve(self, request: ApprovalRequest) -> ApprovalDecision:
        existing = self._store.find(request)
        if existing is not None:
            return existing
        decision = await self._provider.decide(request)
        if decision.approved:
            self._store.save(request, decision)
        return decision

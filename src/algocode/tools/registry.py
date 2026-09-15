"""Tool registry and execution policy."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace

from algocode.approval.service import ApprovalService
from algocode.approval.types import ApprovalRequest
from algocode.policy.engine import PolicyEngine
from algocode.policy.types import PolicyEffect, PolicyRequest
from algocode.sandbox.local import LocalProcessSandbox, SandboxRequest
from algocode.security import SecretRedactor
from algocode.tools.types import ToolContext, ToolDefinition, ToolResult

ToolHandler = Callable[[ToolContext, dict[str, object]], Awaitable[ToolResult]]


class ToolRegistry:
    """Register tool definitions and execute them under security gates."""

    def __init__(
        self,
        *,
        allowed_permissions: set[str] | None = None,
        policy_engine: PolicyEngine | None = None,
        approval_service: ApprovalService | None = None,
        sandbox: LocalProcessSandbox | None = None,
        redactor: SecretRedactor | None = None,
    ) -> None:
        self._tools: dict[str, tuple[ToolDefinition, ToolHandler]] = {}
        self._allowed_permissions = allowed_permissions or {"allow"}
        self._policy_engine = policy_engine
        self._approval_service = approval_service
        self._sandbox = sandbox
        self._redactor = redactor or SecretRedactor()

    def register(self, definition: ToolDefinition, handler: ToolHandler) -> None:
        if definition.name in self._tools:
            raise ValueError(f"tool {definition.name} is already registered")
        self._tools[definition.name] = (definition, handler)

    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(definition for definition, _ in self._tools.values())

    def provider_schemas(self) -> tuple[dict[str, object], ...]:
        return tuple(
            {
                "name": definition.name,
                "description": definition.description,
                "input_schema": definition.input_schema,
            }
            for definition in self.definitions()
        )

    async def execute(
        self,
        name: str,
        arguments: dict[str, object],
        context: ToolContext,
    ) -> ToolResult:
        registered = self._tools.get(name)
        if registered is None:
            return ToolResult(status="error", summary=f"unknown tool: {name}")
        definition, handler = registered
        if definition.permission not in self._allowed_permissions:
            return ToolResult(
                status="error",
                summary=f"tool {name} requires permission {definition.permission}",
            )
        missing = [
            key
            for key, schema in definition.input_schema.items()
            if isinstance(schema, dict) and schema.get("required") is True and key not in arguments
        ]
        if missing:
            return ToolResult(
                status="error",
                summary=f"missing required arguments: {', '.join(missing)}",
            )

        policy_request = _policy_request(definition, arguments)
        policy_decision = (
            self._policy_engine.evaluate(policy_request)
            if self._policy_engine is not None
            else None
        )
        security: dict[str, object] = {}
        if policy_decision is not None:
            security["policy"] = {
                "effect": policy_decision.effect.value,
                "reason": policy_decision.reason,
                "layer": policy_decision.layer.value if policy_decision.layer else None,
                "hash": self._policy_engine.hash(),
            }
            if policy_decision.effect is PolicyEffect.DENY:
                return ToolResult(
                    status="error",
                    summary=f"policy denied {name}: {policy_decision.reason}",
                    structured=security,
                )
            if policy_decision.effect is PolicyEffect.ASK:
                if self._approval_service is None:
                    return ToolResult(
                        status="error",
                        summary=f"approval unavailable for {name}",
                        structured=security,
                    )
                approval = await self._approval_service.resolve(
                    ApprovalRequest(
                        task_id=str(context.task.id),
                        project_id=str(context.task.project_id),
                        action=policy_request.action,
                        resource=policy_request.resource,
                        reason=policy_decision.reason,
                    )
                )
                security["approval"] = {
                    "approved": approval.approved,
                    "scope": approval.scope.value,
                    "reason": approval.reason,
                }
                if not approval.approved:
                    return ToolResult(
                        status="error",
                        summary=f"approval denied for {name}: {approval.reason}",
                        structured=security,
                    )

        if self._sandbox is not None and definition.effects in {"write", "execute"}:
            sandbox = self._sandbox.authorize(
                SandboxRequest(
                    action=policy_request.action,
                    workspace=context.workspace,
                    network=False,
                )
            )
            security["sandbox"] = {
                "allowed": sandbox.allowed,
                "reason": sandbox.reason,
            }
            if not sandbox.allowed:
                return ToolResult(
                    status="error",
                    summary=f"sandbox denied {name}: {sandbox.reason}",
                    structured=security,
                )

        try:
            result = await asyncio.wait_for(
                handler(context, arguments),
                timeout=definition.timeout_seconds,
            )
        except TimeoutError:
            result = ToolResult(status="interrupted", summary=f"tool {name} timed out")
        except Exception as exc:
            result = ToolResult(status="error", summary=f"tool {name} failed: {exc}")
        if security:
            result = replace(
                result,
                structured={**result.structured, **security},
            )
        return replace(
            result,
            summary=self._redactor.redact_text(result.summary),
            structured=self._redactor.redact_value(result.structured),
        )


def _policy_request(
    definition: ToolDefinition,
    arguments: dict[str, object],
) -> PolicyRequest:
    action = {
        "read": "file.read",
        "write": "file.write",
        "execute": "process.execute",
        "control": "control",
    }.get(definition.effects, f"tool.{definition.name}")
    resource = str(arguments.get("uri", arguments.get("path", definition.name)))
    return PolicyRequest(
        action=action,
        resource=resource,
        tool_name=definition.name,
    )

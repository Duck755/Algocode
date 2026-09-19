"""Tool catalog package."""

from algocode.tools.builtins.actions import register_action_tools
from algocode.tools.builtins.filesystem import register_read_tools
from algocode.tools.builtins.shell import register_shell_tool, shell_definition
from algocode.tools.registry import ToolRegistry


def build_default_registry(
    *,
    policy_engine=None,
    approval_service=None,
    sandbox=None,
    redactor=None,
) -> ToolRegistry:
    registry = ToolRegistry(
        policy_engine=policy_engine,
        approval_service=approval_service,
        sandbox=sandbox,
        redactor=redactor,
    )
    register_read_tools(registry)
    register_action_tools(registry)
    return registry


__all__ = [
    "ToolRegistry",
    "build_default_registry",
    "register_shell_tool",
    "shell_definition",
]

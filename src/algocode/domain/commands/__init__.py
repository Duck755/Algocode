"""Domain commands."""

from enum import StrEnum


class CommandType(StrEnum):
    CREATE_TASK = "create_task"
    CAPTURE_BASELINE = "capture_baseline"
    CREATE_CANDIDATE = "create_candidate"
    FREEZE_CANDIDATE = "freeze_candidate"
    START_EXPERIMENT = "start_experiment"
    COMPLETE_EXPERIMENT = "complete_experiment"
    MAKE_DECISION = "make_decision"
    APPLY_CANDIDATE = "apply_candidate"
    ROLLBACK_CANDIDATE = "rollback_candidate"
    CANCEL_TASK = "cancel_task"


__all__ = ["CommandType"]

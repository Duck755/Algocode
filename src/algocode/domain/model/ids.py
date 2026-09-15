"""Typed identifiers used by the domain model."""

from __future__ import annotations

from typing import NewType
from uuid import uuid4

TaskId = NewType("TaskId", str)
CandidateId = NewType("CandidateId", str)
ExperimentId = NewType("ExperimentId", str)
DecisionId = NewType("DecisionId", str)
ProjectId = NewType("ProjectId", str)


def _new(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def new_task_id() -> TaskId:
    return TaskId(_new("task"))


def new_candidate_id() -> CandidateId:
    return CandidateId(_new("cand"))


def new_experiment_id() -> ExperimentId:
    return ExperimentId(_new("exp"))


def new_decision_id() -> DecisionId:
    return DecisionId(_new("dec"))


def new_project_id() -> ProjectId:
    return ProjectId(_new("prj"))

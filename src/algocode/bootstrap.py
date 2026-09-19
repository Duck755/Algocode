"""Application composition root."""

from dataclasses import dataclass
from pathlib import Path

from algocode.application.services import (
    ApplyService,
    BaselineService,
    BenchmarkService,
    CandidateService,
    CorrectnessService,
    DecisionService,
    ExperimentService,
    MaintenanceService,
    ProjectService,
    ReportService,
    SearchArchiveService,
    TaskService,
)
from algocode.approval.service import (
    ApprovalService,
    ConsoleApprovalProvider,
    NonInteractiveApprovalProvider,
)
from algocode.config import AlgocodeConfig, load_config
from algocode.languages import LanguageRegistry
from algocode.policy.engine import PolicyEngine
from algocode.policy.types import PolicyEffect, PolicyLayer, PolicyRule
from algocode.resources import LocalResourceProvider
from algocode.sandbox.local import LocalProcessSandbox
from algocode.sandbox.runner import SandboxProcessRunner
from algocode.security import SecretRedactor
from algocode.storage.artifacts import FileArtifactStore
from algocode.storage.events import SqliteEventStore
from algocode.storage.paths import default_data_dir, project_data_dir
from algocode.storage.sqlite import Database
from algocode.storage.sqlite.approval_store import ApprovalStore
from algocode.storage.sqlite.projections.baseline_projection import BaselineProjection
from algocode.storage.sqlite.projections.benchmark_projection import BenchmarkProjection
from algocode.storage.sqlite.projections.candidate_projection import CandidateProjection
from algocode.storage.sqlite.projections.correctness_projection import CorrectnessProjection
from algocode.storage.sqlite.projections.decision_projection import DecisionProjection
from algocode.storage.sqlite.projections.experiment_projection import ExperimentProjection
from algocode.storage.sqlite.projections.project_projection import ProjectProjection
from algocode.storage.sqlite.projections.task_projection import TaskProjection
from algocode.tools import build_default_registry
from algocode.workspace import GitWorkspaceManager


@dataclass(frozen=True, slots=True)
class AppContext:
    """Fully initialized local application context."""

    config: AlgocodeConfig
    data_dir: Path
    database: Database
    event_store: SqliteEventStore
    artifact_store: FileArtifactStore
    secret_redactor: SecretRedactor
    language_registry: LanguageRegistry
    project_service: ProjectService
    task_service: TaskService
    baseline_service: BaselineService
    correctness_service: CorrectnessService
    benchmark_service: BenchmarkService
    candidate_service: CandidateService
    resource_provider: LocalResourceProvider
    decision_service: DecisionService
    experiment_service: ExperimentService
    maintenance_service: MaintenanceService
    search_archive_service: SearchArchiveService
    apply_service: ApplyService
    report_service: ReportService
    policy_engine: PolicyEngine
    approval_service: ApprovalService
    sandbox: LocalProcessSandbox
    tool_registry: object


def build_context(
    project_root: str | Path | None = None,
    data_dir: str | Path | None = None,
    approval_provider=None,
) -> AppContext:
    """Load configuration and initialize local persistence."""

    if data_dir is not None:
        resolved_data_dir = Path(data_dir).expanduser()
        project_cache = project_data_dir(project_root) if project_root is not None else None
        config_data_dir = (
            default_data_dir()
            if project_cache is not None and resolved_data_dir.resolve() == project_cache.resolve()
            else resolved_data_dir
        )
    elif project_root is not None:
        resolved_data_dir = project_data_dir(project_root)
        config_data_dir = default_data_dir()
    else:
        resolved_data_dir = default_data_dir()
        config_data_dir = resolved_data_dir
    config = load_config(project_root=project_root, data_dir=config_data_dir)
    secret_redactor = SecretRedactor.from_config(config)
    database = Database(resolved_data_dir)
    database.initialize()
    task_projection = TaskProjection()
    project_projection = ProjectProjection()
    baseline_projection = BaselineProjection()
    correctness_projection = CorrectnessProjection()
    benchmark_projection = BenchmarkProjection()
    candidate_projection = CandidateProjection()
    decision_projection = DecisionProjection()
    experiment_projection = ExperimentProjection()
    event_store = SqliteEventStore(
        database,
        projectors=(
            task_projection,
            project_projection,
            baseline_projection,
            correctness_projection,
            benchmark_projection,
            candidate_projection,
            decision_projection,
            experiment_projection,
        ),
        redactor=secret_redactor,
    )
    sandbox_runner = SandboxProcessRunner(config.policy.sandbox)
    language_registry = LanguageRegistry(sandbox_runner)
    artifact_store = FileArtifactStore(
        resolved_data_dir / "artifacts",
        redactor=secret_redactor,
    )
    policy_engine = PolicyEngine(
        rules=tuple(
            PolicyRule(
                action=rule.action,
                resource=rule.resource,
                effect=PolicyEffect(rule.effect),
                layer=PolicyLayer(rule.layer),
            )
            for rule in config.policy.rules
        ),
        default_effect=PolicyEffect(config.policy.default_effect),
        protected_files=config.correctness.protected_files,
    )
    approval_service = ApprovalService(
        ApprovalStore(database, redactor=secret_redactor),
        approval_provider
        or (
            ConsoleApprovalProvider()
            if config.policy.approval.mode == "interactive"
            else NonInteractiveApprovalProvider()
        ),
    )
    sandbox = LocalProcessSandbox(config.policy.sandbox, sandbox_runner)
    task_service = TaskService(
        event_store=event_store,
        database=database,
        task_projection=task_projection,
    )
    project_service = ProjectService(
        event_store=event_store,
        database=database,
        project_projection=project_projection,
        language_registry=language_registry,
    )
    baseline_service = BaselineService(
        event_store=event_store,
        database=database,
        task_service=task_service,
        project_service=project_service,
        baseline_projection=baseline_projection,
        language_registry=language_registry,
        artifact_store=artifact_store,
        workspace_manager_factory=lambda repository: GitWorkspaceManager(
            repository, resolved_data_dir
        ),
    )
    correctness_service = CorrectnessService(
        event_store=event_store,
        database=database,
        task_service=task_service,
        project_service=project_service,
        baseline_service=baseline_service,
        correctness_projection=correctness_projection,
        language_registry=language_registry,
        artifact_store=artifact_store,
    )
    benchmark_service = BenchmarkService(
        event_store=event_store,
        database=database,
        task_service=task_service,
        project_service=project_service,
        baseline_service=baseline_service,
        correctness_service=correctness_service,
        benchmark_projection=benchmark_projection,
        language_registry=language_registry,
        artifact_store=artifact_store,
        lock_root=resolved_data_dir / "locks",
    )
    candidate_service = CandidateService(
        event_store=event_store,
        database=database,
        task_service=task_service,
        project_service=project_service,
        baseline_service=baseline_service,
        candidate_projection=candidate_projection,
        data_dir=resolved_data_dir,
    )
    resource_provider = LocalResourceProvider(
        artifact_store=artifact_store,
        task_service=task_service,
        baseline_service=baseline_service,
        candidate_service=candidate_service,
        benchmark_service=benchmark_service,
    )
    decision_service = DecisionService(
        event_store=event_store,
        database=database,
        task_service=task_service,
        candidate_service=candidate_service,
        correctness_service=correctness_service,
        benchmark_service=benchmark_service,
        decision_projection=decision_projection,
        acceptance_policy=config.acceptance_policy,
    )
    experiment_service = ExperimentService(
        event_store=event_store,
        database=database,
        experiment_projection=experiment_projection,
    )
    search_archive_service = SearchArchiveService(
        task_service=task_service,
        candidate_service=candidate_service,
        correctness_service=correctness_service,
        decision_service=decision_service,
        benchmark_service=benchmark_service,
    )
    maintenance_service = MaintenanceService(
        data_dir=resolved_data_dir,
        database=database,
        artifact_store=artifact_store,
        retention_days=config.storage.artifact_retention_days,
    )
    apply_service = ApplyService(
        event_store=event_store,
        task_service=task_service,
        project_service=project_service,
        baseline_service=baseline_service,
        candidate_service=candidate_service,
        decision_service=decision_service,
        artifact_store=artifact_store,
        data_dir=resolved_data_dir,
    )
    report_service = ReportService(
        event_store=event_store,
        task_service=task_service,
        project_service=project_service,
        baseline_service=baseline_service,
        candidate_service=candidate_service,
        correctness_service=correctness_service,
        benchmark_service=benchmark_service,
        decision_service=decision_service,
        artifact_store=artifact_store,
        redactor=secret_redactor,
    )
    tool_registry = build_default_registry(
        policy_engine=policy_engine,
        approval_service=approval_service,
        sandbox=sandbox,
        redactor=secret_redactor,
    )
    return AppContext(
        config=config,
        data_dir=resolved_data_dir,
        database=database,
        event_store=event_store,
        artifact_store=artifact_store,
        secret_redactor=secret_redactor,
        language_registry=language_registry,
        project_service=project_service,
        task_service=task_service,
        baseline_service=baseline_service,
        correctness_service=correctness_service,
        benchmark_service=benchmark_service,
        candidate_service=candidate_service,
        resource_provider=resource_provider,
        decision_service=decision_service,
        experiment_service=experiment_service,
        maintenance_service=maintenance_service,
        search_archive_service=search_archive_service,
        apply_service=apply_service,
        report_service=report_service,
        policy_engine=policy_engine,
        approval_service=approval_service,
        sandbox=sandbox,
        tool_registry=tool_registry,
    )

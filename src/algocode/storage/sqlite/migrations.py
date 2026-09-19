"""Versioned SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    statements: tuple[str, ...]


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                objective TEXT NOT NULL,
                status TEXT NOT NULL,
                current_phase TEXT NOT NULL,
                baseline_id TEXT,
                active_candidate_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS event_log (
                id TEXT PRIMARY KEY,
                aggregate_id TEXT NOT NULL,
                seq INTEGER NOT NULL,
                type TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                artifact_refs_json TEXT NOT NULL,
                UNIQUE(aggregate_id, seq)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_event_log_aggregate_seq
            ON event_log(aggregate_id, seq)
            """,
        ),
    ),
    Migration(
        version=2,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                root_path TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                language TEXT NOT NULL,
                git_revision TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS baselines (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                revision TEXT NOT NULL,
                snapshot_hash TEXT NOT NULL,
                environment_hash TEXT NOT NULL,
                build_result_ref_json TEXT,
                correctness_result_ref_json TEXT,
                benchmark_result_ref_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_baselines_task_created
            ON baselines(task_id, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=3,
        statements=(
            "ALTER TABLE baselines ADD COLUMN workspace_ref TEXT",
            """
            CREATE TABLE IF NOT EXISTS correctness_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                workspace_ref TEXT NOT NULL,
                spec_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                spec_ref_json TEXT NOT NULL,
                result_ref_json TEXT,
                failure_kind TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_correctness_task_started
            ON correctness_runs(task_id, started_at DESC)
            """,
        ),
    ),
    Migration(
        version=4,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS benchmark_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                workspace_ref TEXT NOT NULL,
                spec_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                environment_hash TEXT NOT NULL,
                comparison_key TEXT NOT NULL,
                status TEXT NOT NULL,
                result_ref_json TEXT,
                comparison_ref_json TEXT,
                correctness_result_id TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS benchmark_samples (
                id TEXT PRIMARY KEY,
                benchmark_run_id TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                sample_index INTEGER NOT NULL,
                metric TEXT NOT NULL,
                value REAL NOT NULL,
                valid INTEGER NOT NULL,
                message TEXT NOT NULL,
                FOREIGN KEY(benchmark_run_id) REFERENCES benchmark_runs(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_task_started
            ON benchmark_runs(task_id, started_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_benchmark_samples_run
            ON benchmark_samples(benchmark_run_id, target_kind, sample_index)
            """,
        ),
    ),
    Migration(
        version=5,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                base_revision TEXT NOT NULL,
                base_snapshot_hash TEXT NOT NULL,
                workspace_ref TEXT NOT NULL,
                status TEXT NOT NULL,
                patch_hash TEXT,
                created_at TEXT NOT NULL,
                frozen_at TEXT,
                FOREIGN KEY(task_id) REFERENCES tasks(id)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS decisions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                outcome TEXT NOT NULL,
                reason TEXT NOT NULL,
                evidence_refs_json TEXT NOT NULL,
                decided_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(candidate_id) REFERENCES candidates(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_candidates_task_created
            ON candidates(task_id, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_decisions_task_decided
            ON decisions(task_id, decided_at DESC)
            """,
        ),
    ),
    Migration(
        version=6,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                project_id TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT NOT NULL,
                scope TEXT NOT NULL,
                approved INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_approvals_task_action
            ON approvals(task_id, action, resource, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_approvals_project_action
            ON approvals(project_id, action, resource, created_at DESC)
            """,
        ),
    ),
    Migration(
        version=7,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS task_run_locks (
                task_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )
            """,
        ),
    ),
    Migration(
        version=8,
        statements=(
            "ALTER TABLE candidates ADD COLUMN parent_candidate_id TEXT",
            "ALTER TABLE candidates ADD COLUMN fork_snapshot_hash TEXT",
            "ALTER TABLE candidates ADD COLUMN apply_base_revision TEXT",
            "ALTER TABLE candidates ADD COLUMN apply_base_snapshot_hash TEXT",
            """
            UPDATE candidates
            SET fork_snapshot_hash = base_snapshot_hash
            WHERE fork_snapshot_hash IS NULL
            """,
            """
            UPDATE candidates
            SET apply_base_revision = (
                    SELECT b.revision
                    FROM baselines AS b
                    WHERE b.task_id = candidates.task_id
                    ORDER BY b.created_at DESC
                    LIMIT 1
                ),
                apply_base_snapshot_hash = (
                    SELECT b.snapshot_hash
                    FROM baselines AS b
                    WHERE b.task_id = candidates.task_id
                    ORDER BY b.created_at DESC
                    LIMIT 1
                )
            WHERE apply_base_snapshot_hash IS NULL
            """,
        ),
    ),
    Migration(
        version=9,
        statements=(
            """
            ALTER TABLE benchmark_samples
            ADD COLUMN input_id TEXT NOT NULL DEFAULT ''
            """,
        ),
    ),
    Migration(
        version=10,
        statements=(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                baseline_id TEXT NOT NULL,
                candidate_id TEXT NOT NULL,
                spec_hash TEXT NOT NULL,
                input_hash TEXT NOT NULL,
                environment_hash TEXT NOT NULL,
                comparison_key TEXT NOT NULL,
                policy_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                decision TEXT,
                started_at TEXT,
                completed_at TEXT,
                invalidation_reason TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(task_id) REFERENCES tasks(id),
                FOREIGN KEY(candidate_id) REFERENCES candidates(id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_experiments_task_created
            ON experiments(task_id, created_at DESC)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_experiments_candidate
            ON experiments(candidate_id, created_at DESC)
            """,
        ),
    ),
)


def apply_migrations(connection: sqlite3.Connection) -> None:
    """Apply all migrations not yet recorded by the database."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {
        int(row["version"])
        for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for migration in MIGRATIONS:
        if migration.version in applied:
            continue
        for statement in migration.statements:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (migration.version, datetime.now(UTC).isoformat()),
        )

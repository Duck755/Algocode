"""Project detection and registration service."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import yaml

from algocode.domain.errors import NotFoundError
from algocode.domain.events import EventEnvelope, EventType
from algocode.domain.model import Language, Project, ProjectId
from algocode.languages import LanguageRegistry
from algocode.ports import EventStore
from algocode.storage.sqlite.database import Database
from algocode.storage.sqlite.projections.project_projection import ProjectProjection
from algocode.workspace.git import GitRepository


class ProjectService:
    """Register local Git projects with stable identifiers."""

    def __init__(
        self,
        event_store: EventStore,
        database: Database,
        project_projection: ProjectProjection,
        language_registry: LanguageRegistry,
    ) -> None:
        self._event_store = event_store
        self._database = database
        self._project_projection = project_projection
        self._language_registry = language_registry

    async def register(
        self,
        path: str | Path,
        *,
        language: Language | str = Language.AUTO,
        write_config: bool = False,
    ) -> Project:
        repository = await GitRepository.discover(path)
        root = repository.root
        revision = await repository.head_revision()
        detected = await self._language_registry.detect(root)
        selected_language = self._language_registry.resolve_language(language, detected)
        now = datetime.now(UTC)
        existing = await self.get_by_root(root)
        project = Project(
            id=_project_id(root),
            root_path=str(root),
            name=root.name or str(root),
            language=selected_language,
            git_revision=revision,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )
        events = await self._event_store.read(str(project.id))
        next_seq = events[-1].seq + 1 if events else 1
        event = EventEnvelope(
            id=f"evt_{uuid4().hex}",
            aggregate_id=str(project.id),
            seq=next_seq,
            type=EventType.PROJECT_REGISTERED,
            timestamp=now,
            payload={
                "project_id": str(project.id),
                "root_path": project.root_path,
                "name": project.name,
                "language": project.language.value,
                "git_revision": project.git_revision,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            },
        )
        expected_seq = next_seq - 1
        await self._event_store.append(str(project.id), expected_seq, (event,))
        if write_config:
            _write_project_config(root, project.language)
        return project

    async def get(self, project_id: ProjectId | str) -> Project:
        with self._database.connect() as connection:
            project = self._project_projection.get(connection, str(project_id))
        if project is None:
            raise NotFoundError(f"project {project_id} was not found")
        return project

    async def get_by_root(self, root: str | Path) -> Project | None:
        resolved = str(Path(root).resolve())
        with self._database.connect() as connection:
            return self._project_projection.get_by_root(connection, resolved)

    async def list(self) -> list[Project]:
        with self._database.connect() as connection:
            return self._project_projection.list(connection)


def _project_id(root: Path) -> ProjectId:
    normalized = str(root.resolve()).casefold().encode("utf-8")
    digest = hashlib.sha256(normalized).hexdigest()[:24]
    return ProjectId(f"prj_{digest}")


def _write_project_config(root: Path, language: Language) -> None:
    path = root / ".algocode.yaml"
    if path.exists():
        return
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "project": {
                    "language": language.value,
                    "source_root": ".",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

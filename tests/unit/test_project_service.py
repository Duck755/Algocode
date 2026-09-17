from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.bootstrap import build_context
from algocode.domain.events import EventType
from algocode.domain.model import Language
from tests.support.git import init_git_repository


class ProjectServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.project_root = init_git_repository(
            self.root / "project",
            {"main.py": "print('hello')\n"},
        )
        self.context = build_context(data_dir=self.root / "data")

    async def asyncTearDown(self) -> None:
        self.temporary_directory.cleanup()

    async def test_register_project_is_stable_and_persistent(self) -> None:
        first = await self.context.project_service.register(self.project_root, write_config=True)
        second = await self.context.project_service.register(self.project_root)

        self.assertEqual(first.id, second.id)
        self.assertEqual(first.language, Language.PYTHON)
        self.assertEqual(first.created_at, second.created_at)
        self.assertEqual(first.git_revision, second.git_revision)
        self.assertTrue((self.project_root / ".algocode" / "config.yaml").exists())
        restored = await self.context.project_service.get(first.id)
        self.assertEqual(restored.id, first.id)
        self.assertEqual(restored.language, first.language)
        projects = await self.context.project_service.list()
        self.assertEqual([project.id for project in projects], [first.id])

        events = await self.context.event_store.read(str(first.id))
        self.assertEqual(
            [event.type for event in events],
            [
                EventType.PROJECT_REGISTERED,
                EventType.PROJECT_REGISTERED,
            ],
        )


if __name__ == "__main__":
    unittest.main()

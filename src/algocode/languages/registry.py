"""Language adapter selection and project detection."""

from __future__ import annotations

from pathlib import Path

from algocode.domain.model import Language
from algocode.languages.cpp import CppLanguageAdapter
from algocode.languages.python import PythonLanguageAdapter
from algocode.languages.types import ProjectInfo


class LanguageRegistry:
    """Combine language adapters behind one detection interface."""

    def __init__(self, sandbox_runner=None) -> None:
        self.sandbox_runner = sandbox_runner
        self._adapters = {
            Language.CPP: CppLanguageAdapter(sandbox_runner),
            Language.PYTHON: PythonLanguageAdapter(sandbox_runner),
        }

    async def detect(self, root: Path) -> ProjectInfo:
        infos: list[ProjectInfo] = []
        for adapter in self._adapters.values():
            info = await adapter.detect(root)
            if info is not None:
                infos.append(info)
        languages = tuple(
            sorted(
                {language for info in infos for language in info.languages},
                key=lambda language: language.value,
            )
        )
        build_systems = tuple(info.build_system for info in infos if info.build_system)
        return ProjectInfo(
            root=root.resolve(),
            languages=languages,
            build_system="+".join(build_systems) if build_systems else None,
        )

    def adapter_for(self, language: Language):
        try:
            return self._adapters[language]
        except KeyError as exc:
            raise ValueError(f"unsupported language: {language}") from exc

    def resolve_language(
        self,
        requested: Language | str,
        detected: ProjectInfo,
    ) -> Language:
        language = Language(requested)
        if language is not Language.AUTO:
            if language not in detected.languages:
                raise ValueError(f"{language.value} project files were not detected")
            return language
        if detected.primary_language is None:
            raise ValueError("no supported C++ or Python project was detected")
        return detected.primary_language

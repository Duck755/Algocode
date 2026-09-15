"""Language adapters."""

from algocode.languages.cpp import CppLanguageAdapter
from algocode.languages.python import PythonLanguageAdapter
from algocode.languages.registry import LanguageRegistry

__all__ = ["CppLanguageAdapter", "LanguageRegistry", "PythonLanguageAdapter"]

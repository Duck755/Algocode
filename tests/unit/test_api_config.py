from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from algocode.cli.commands.api import (
    ProviderSelection,
    _active_model,
    _ask_model,
    _configured_model_ids,
    _secret_fingerprint,
    persist_provider_selection,
)
from algocode.cli.commands.model import ModelChoice, _merge_model_choices
from algocode.security import CredentialStore


class ApiConfigHelpersTests(unittest.TestCase):
    def test_model_choices_merge_upstream_and_configured_models(self) -> None:
        models = {"openai/configured": SimpleNamespace(provider="openai", model="configured")}

        choices = _merge_model_choices(
            models,
            "openai",
            ["upstream-a", "configured", "upstream-a"],
            "openai/upstream-a",
        )

        self.assertEqual(
            [(choice.model_id, choice.model_key, choice.configured) for choice in choices],
            [
                ("upstream-a", "openai/upstream-a", False),
                ("configured", "openai/configured", True),
            ],
        )
        self.assertEqual(
            _merge_model_choices({}, "openai", ["fresh"], "openai/missing"),
            [
                ModelChoice(
                    model_key="openai/fresh",
                    model_id="fresh",
                    configured=False,
                )
            ],
        )

    def test_secret_fingerprint_hides_middle(self) -> None:
        self.assertEqual(_secret_fingerprint("sk-1234567890abcdef"), "sk-123...cdef")
        self.assertEqual(_secret_fingerprint("short"), "********")

    def test_active_model_reads_default_model_key(self) -> None:
        config = {
            "defaults": {"provider": "openai", "model": "openai/gpt-5.6"},
            "models": {
                "openai/gpt-5.6": {"provider": "openai", "model": "gpt-5.6"},
            },
        }

        self.assertEqual(_active_model(config, "openai"), "gpt-5.6")
        self.assertEqual(_active_model(config, "deepseek"), "")
        self.assertEqual(_configured_model_ids(config, "openai"), ["gpt-5.6"])
        self.assertEqual(_configured_model_ids(config, "deepseek"), [])

    def test_ask_model_merges_upstream_default_and_configured_models(self) -> None:
        config = {
            "defaults": {"provider": "openai", "model": "openai/gpt-5.6"},
            "models": {
                "openai/gpt-5.6": {"provider": "openai", "model": "gpt-5.6"},
                "openai/configured": {"provider": "openai", "model": "configured"},
            },
        }

        class FakeSelect:
            def __init__(self, choices):
                self.choices = choices

            def ask(self):
                return self.choices[0].value

        captured = []

        def fake_select(message, choices, default=None):
            captured.extend(choices)
            return FakeSelect(choices)

        with patch("algocode.cli.commands.api._select", side_effect=fake_select):
            selected = _ask_model(config, "openai", "gpt-5.6", ["upstream-a", "gpt-5.6"])

        titles = [choice.title for choice in captured]
        self.assertEqual(selected, "upstream-a")
        self.assertEqual(
            titles,
            ["upstream-a", "gpt-5.6", "configured", "Enter another model ID..."],
        )

    def test_persist_provider_selection_stores_credential_outside_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            selection = ProviderSelection(
                provider_key="openai",
                provider_type="openai-compatible",
                base_url="https://api.openai.com/v1",
                model_id="gpt-5.6",
                context_window=128_000,
                api_key="sk-test-key",
            )

            with (
                patch(
                    "algocode.security.credentials.default_data_dir",
                    return_value=data_dir,
                ),
                patch(
                    "algocode.config.global_file.default_data_dir",
                    return_value=data_dir,
                ),
            ):
                config_path = persist_provider_selection(selection)

            config_text = config_path.read_text(encoding="utf-8")
            config = yaml.safe_load(config_text)
            self.assertEqual(
                config["providers"]["openai"]["credential_ref"],
                "local://openai",
            )
            self.assertEqual(config["defaults"]["model"], "openai/gpt-5.6")
            self.assertNotIn("sk-test-key", config_text)
            self.assertEqual(
                CredentialStore(data_dir / "credentials.json").get("openai"),
                "sk-test-key",
            )

    def test_persist_provider_selection_supports_env_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_dir = Path(directory)
            selection = ProviderSelection(
                provider_key="openai",
                provider_type="openai-compatible",
                base_url="https://api.openai.com/v1",
                model_id="gpt-5.6",
                context_window=128_000,
                api_key="",
                api_key_env="OPENAI_API_KEY",
            )

            with (
                patch(
                    "algocode.security.credentials.default_data_dir",
                    return_value=data_dir,
                ),
                patch(
                    "algocode.config.global_file.default_data_dir",
                    return_value=data_dir,
                ),
            ):
                config_path = persist_provider_selection(selection)

            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertEqual(
                config["providers"]["openai"]["api_key_env"],
                "OPENAI_API_KEY",
            )
            self.assertNotIn("credential_ref", config["providers"]["openai"])


if __name__ == "__main__":
    unittest.main()

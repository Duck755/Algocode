from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from algocode.cli.commands.api import PRESETS
from algocode.cli.main import app
from algocode.security import CredentialStore
from tests.support.mock_openai import MockOpenAIServer


class CliApiModelTestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_api_saves_provider_and_model_selects_default(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            data_dir = Path(directory) / "data"
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch(
                    "algocode.security.credentials.default_data_dir",
                    return_value=data_dir,
                ), patch(
                    "algocode.config.global_file.default_data_dir",
                    return_value=data_dir,
                ), patch(
                    "algocode.cli.commands.model.default_data_dir",
                    return_value=data_dir,
                ), patch(
                    "algocode.cli.commands.model.list_models",
                    return_value=[],
                ):
                    result = self.runner.invoke(
                        app,
                        ["api"],
                        input="2\n\n\n\nsk-test-key\n",
                    )
                    model_result = self.runner.invoke(app, ["model"], input="1\n")
            finally:
                os.chdir(previous)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertEqual(model_result.exit_code, 0, model_result.output)
            config_path = data_dir / "config.yaml"
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["defaults"]["provider"], "deepseek")
            deepseek_preset = next(preset for preset in PRESETS if preset.key == "deepseek")
            self.assertEqual(
                config["defaults"]["model"],
                f"deepseek/{deepseek_preset.default_model}",
            )
            self.assertEqual(
                config["providers"]["deepseek"]["credential_ref"],
                "local://deepseek",
            )
            self.assertNotIn("sk-test-key", config_path.read_text(encoding="utf-8"))
            self.assertFalse((root / ".algocode/config.local.yaml").exists())
            self.assertEqual(
                CredentialStore(data_dir / "credentials.json").get("deepseek"),
                "sk-test-key",
            )

    def test_model_command_uses_upstream_models(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            data_dir = Path(directory) / "data"
            data_dir.mkdir()
            config_path = data_dir / "config.yaml"
            config_path.write_text(
                """
providers:
  mock:
    type: openai-compatible
    base_url: https://example.test/v1
    credential_ref: local://mock
models:
  mock/old:
    provider: mock
    model: old
    context_window: 4096
defaults:
  provider: mock
  model: mock/old
""",
                encoding="utf-8",
            )
            CredentialStore(data_dir / "credentials.json").set("mock", "mock-key")

            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch(
                    "algocode.cli.commands.model.default_data_dir",
                    return_value=data_dir,
                ), patch(
                    "algocode.config.global_file.default_data_dir",
                    return_value=data_dir,
                ), patch(
                    "algocode.cli.commands.model.resolve_api_key",
                    return_value="mock-key",
                ), patch(
                    "algocode.cli.commands.model.list_models",
                    return_value=["new-model", "old"],
                ):
                    result = self.runner.invoke(app, ["model"], input="1\n")
            finally:
                os.chdir(previous)

            self.assertEqual(result.exit_code, 0, result.output)
            self.assertIn("new-model", result.output)
            config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            self.assertEqual(config["defaults"]["model"], "mock/new-model")
            self.assertEqual(
                config["models"]["mock/new-model"]["model"],
                "new-model",
            )

    def test_test_command_uses_selected_model_and_sends_system_variable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            data_dir = Path(directory) / "data"
            data_dir.mkdir()
            config_path = data_dir / "config.yaml"
            config_path.write_text(
                """
providers:
  mock:
    type: openai-compatible
    base_url: PLACEHOLDER
    credential_ref: local://mock
models:
  mock/test-model:
    provider: mock
    model: mock-test-model
    context_window: 4096
defaults:
  provider: mock
  model: mock/test-model
""",
                encoding="utf-8",
            )

            with MockOpenAIServer() as server:
                document = yaml.safe_load(config_path.read_text(encoding="utf-8"))
                document["providers"]["mock"]["base_url"] = server.base_url
                config_path.write_text(
                    yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
                    encoding="utf-8",
                )
                CredentialStore(data_dir / "credentials.json").set("mock", "mock-key")
                server.enqueue_text("你好，我是 mock-test-model。")

                previous = Path.cwd()
                try:
                    os.chdir(root)
                    with patch(
                        "algocode.security.credentials.default_data_dir",
                        return_value=data_dir,
                    ), patch(
                        "algocode.bootstrap.default_data_dir",
                        return_value=data_dir,
                    ):
                        result = self.runner.invoke(app, ["test", "--json"])
                finally:
                    os.chdir(previous)

            self.assertEqual(result.exit_code, 0, result.output)
            payload = json.loads(result.stdout)["data"]
            self.assertEqual(payload["response"], "你好，我是 mock-test-model。")
            self.assertEqual(payload["model"], "mock-test-model")
            request = server.requests[0]
            self.assertIn("mock-test-model", request["messages"][0]["content"])
            self.assertEqual(request["messages"][1]["content"], "你好，你是什么模型")


if __name__ == "__main__":
    unittest.main()

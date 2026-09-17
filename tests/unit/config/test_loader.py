from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from algocode.config import compute_config_hash, load_config
from algocode.domain.errors import ConfigError


class ConfigLoaderTests(unittest.TestCase):
    def test_defaults_are_loaded_without_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_config(project_root=root, data_dir=root / "data", environ={})

        self.assertEqual(config.version, 1)
        self.assertEqual(config.project.language, "auto")
        self.assertEqual(config.runtime.max_steps_per_phase, 30)
        self.assertEqual(config.benchmark.repeats, 5)
        self.assertEqual(config.models, {})
        self.assertEqual(config.defaults.provider, "default")
        self.assertEqual(config.defaults.model, "default")

    def test_precedence_from_global_to_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "config.yaml").write_text(
                """
models:
  default:
    model: global-model
    context_window: 8192
runtime:
  max_steps_per_phase: 10
""",
                encoding="utf-8",
            )
            (root / ".algocode.yaml").write_text(
                """
runtime:
  max_steps_per_phase: 20
""",
                encoding="utf-8",
            )
            (root / ".algocode.local.yaml").write_text(
                """
runtime:
  max_steps_per_phase: 30
""",
                encoding="utf-8",
            )

            config = load_config(
                project_root=root,
                data_dir=data_dir,
                environ={"ALGOCODE_RUNTIME__MAX_STEPS_PER_PHASE": "40"},
                cli_overrides={"runtime": {"max_steps_per_phase": 50}},
            )

        self.assertEqual(config.runtime.max_steps_per_phase, 50)
        self.assertEqual(config.models["default"].model, "global-model")
        self.assertEqual(config.models["default"].context_window, 8192)

    def test_secret_environment_variables_are_not_config_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_config(
                project_root=root,
                data_dir=root / "data",
                environ={"ALGOCODE_API_KEY": "secret-value"},
            )

        self.assertEqual(config.version, 1)

    def test_environment_values_are_parsed_as_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = load_config(
                project_root=root,
                data_dir=root / "data",
                environ={
                    "ALGOCODE_RUNTIME__NETWORK": "true",
                    "ALGOCODE_BENCHMARK__WARMUP": "3",
                },
            )

        self.assertTrue(config.runtime.network)
        self.assertEqual(config.benchmark.warmup, 3)

    def test_policy_rules_are_tagged_and_appended_across_layers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "config.yaml").write_text(
                "policy:\n  rules:\n    - action: file.read\n      effect: allow\n",
                encoding="utf-8",
            )
            (root / ".algocode.yaml").write_text(
                "policy:\n  rules:\n    - action: file.write\n      effect: deny\n",
                encoding="utf-8",
            )
            config = load_config(project_root=root, data_dir=data_dir, environ={})

        self.assertEqual(len(config.policy.rules), 2)
        self.assertEqual(config.policy.rules[0].layer, "user")
        self.assertEqual(config.policy.rules[1].layer, "project")

    def test_camel_case_p0_keys_and_environment_reference_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "config.yaml").write_text(
                """
providers:
  default:
    type: openai-compatible
    baseUrl: https://api.deepseek.com/v1
    apiKeyEnv: ALGOCODE_API_KEY
models:
  default:
    provider: default
    model: deepseek-chat
    contextWindow: 128000
""",
                encoding="utf-8",
            )
            config = load_config(project_root=root, data_dir=data_dir, environ={})

        self.assertEqual(config.providers["default"].base_url, "https://api.deepseek.com/v1")
        self.assertEqual(config.providers["default"].api_key_env, "ALGOCODE_API_KEY")
        self.assertEqual(config.models["default"].context_window, 128000)

    def test_api_key_env_rejects_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".algocode.yaml").write_text(
                "providers:\n  default:\n    apiKeyEnv: sk-secret-value\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError) as caught:
                load_config(project_root=root, data_dir=root / "data", environ={})

        self.assertNotIn("sk-secret-value", str(caught.exception))

    def test_acceptance_policy_and_benchmark_defaults_are_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".algocode.yaml").write_text(
                """
acceptancePolicy:
  requireCorrectness: true
  minMedianImprovementPercent: 3.5
  maxVariationPercent: 10
benchmarks:
  default:
    warmup: 1
    repeats: 7
""",
                encoding="utf-8",
            )
            config = load_config(project_root=root, data_dir=root / "data", environ={})

        self.assertEqual(config.acceptance_policy.min_median_improvement_percent, 3.5)
        self.assertEqual(config.acceptance_policy.max_variation_percent, 10)
        self.assertEqual(config.benchmarks["default"].repeats, 7)

    def test_local_credential_reference_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".algocode.yaml").write_text(
                "providers:\n  default:\n    credentialRef: local://deepseek\n",
                encoding="utf-8",
            )
            config = load_config(project_root=root, data_dir=root / "data", environ={})

        self.assertEqual(config.providers["default"].credential_ref, "local://deepseek")

    def test_credential_ref_rejects_secret_value(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".algocode.yaml").write_text(
                "providers:\n  default:\n    credentialRef: sk-secret-value\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError) as caught:
                load_config(project_root=root, data_dir=root / "data", environ={})

        self.assertNotIn("sk-secret-value", str(caught.exception))

    def test_unknown_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".algocode.yaml").write_text(
                "runtime:\n  unknown_setting: true\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigError):
                load_config(project_root=root, data_dir=root / "data", environ={})

    def test_config_hash_is_stable_and_content_sensitive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = load_config(project_root=root, data_dir=root / "data", environ={})
            second = load_config(project_root=root, data_dir=root / "data", environ={})
            changed = load_config(
                project_root=root,
                data_dir=root / "data",
                environ={},
                cli_overrides={"runtime": {"max_steps_per_phase": 21}},
            )

        self.assertEqual(compute_config_hash(first), compute_config_hash(second))
        self.assertNotEqual(compute_config_hash(first), compute_config_hash(changed))


if __name__ == "__main__":
    unittest.main()

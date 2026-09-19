from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from algocode.providers.model_catalog import list_models


class ModelCatalogTests(unittest.TestCase):
    def test_list_models_parses_ids_and_dedupes(self) -> None:
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": [
                {"id": "gpt-5.6"},
                {"id": "gpt-5.6"},
                {"id": ""},
                {"not-id": "ignored"},
                {"id": "gpt-5.6-mini"},
            ]
        }

        with patch("algocode.providers.model_catalog.httpx.get", return_value=response) as get:
            models = list_models("openai-compatible", "https://api.openai.com/v1", "key")

        self.assertEqual(models, ["gpt-5.6", "gpt-5.6-mini"])
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer key")

    def test_list_models_returns_empty_on_http_error(self) -> None:
        with patch(
            "algocode.providers.model_catalog.httpx.get",
            side_effect=__import__("httpx").HTTPError("boom"),
        ):
            self.assertEqual(list_models("anthropic", "https://api.anthropic.com", "key"), [])

    def test_list_models_returns_empty_without_credentials(self) -> None:
        self.assertEqual(list_models("responses", "", ""), [])

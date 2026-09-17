from __future__ import annotations

import unittest

from pydantic import BaseModel

from algocode.structured_output import (
    StructuredOutputError,
    parse_json_object,
    parse_model,
)


class ExampleOutput(BaseModel):
    summary: str
    count: int


class StructuredOutputTests(unittest.TestCase):
    def test_parse_json_object_strips_code_fence(self) -> None:
        payload = parse_json_object(
            '```json\n{"summary": "ok", "count": 1}\n```',
            label="example",
        )

        self.assertEqual(payload, {"summary": "ok", "count": 1})

    def test_parse_json_object_repairs_truncated_object(self) -> None:
        payload = parse_json_object('{"summary": "ok"', label="example")

        self.assertEqual(payload["summary"], "ok")

    def test_parse_model_reports_field_path(self) -> None:
        with self.assertRaises(StructuredOutputError) as caught:
            parse_model(
                '{"summary": "ok", "count": "bad"}',
                ExampleOutput,
                label="example",
            )

        self.assertIn("count", str(caught.exception))
        self.assertIn("valid integer", str(caught.exception))


if __name__ == "__main__":
    unittest.main()

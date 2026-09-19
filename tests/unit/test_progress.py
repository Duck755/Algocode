from __future__ import annotations

import io
import unittest

from algocode.cli.progress import (
    StageReporter,
    display_width,
    format_duration,
    render_evidence,
)


class FormatDurationTests(unittest.TestCase):
    def test_formats_each_scale(self) -> None:
        self.assertEqual(format_duration(0.24), "240ms")
        self.assertEqual(format_duration(3.21), "3.2s")
        self.assertEqual(format_duration(42.4), "42s")
        self.assertEqual(format_duration(64), "1m04s")


class StageReporterPlainTests(unittest.TestCase):
    def test_plain_mode_writes_narrative_lines(self) -> None:
        stream = io.StringIO()
        reporter = StageReporter(
            ("扫描", "契约"),
            title="algocode · init",
            stream=stream,
            enabled=True,
            color=False,
            unicode=True,
        )

        reporter.begin("扫描", "检测语言")
        reporter.complete("扫描", "python")
        reporter.begin("契约")
        reporter.note("未配置模型")
        reporter.fail("contract test failed", hint="查看契约测试")
        reporter.close()

        text = stream.getvalue()
        self.assertIn("扫描: 检测语言", text)
        self.assertIn("扫描 ✔ (", text)
        self.assertIn("! 未配置模型", text)
        self.assertIn("契约 failed: contract test failed (查看契约测试)", text)

    def test_ascii_fallback_hides_unicode_glyphs(self) -> None:
        stream = io.StringIO()
        reporter = StageReporter(
            ("扫描",),
            stream=stream,
            enabled=True,
            color=False,
            unicode=False,
        )

        reporter.begin("扫描")
        reporter.complete("扫描")

        text = stream.getvalue()
        self.assertIn("扫描 ok", text)
        self.assertNotIn("✔", text)

    def test_disabled_reporter_is_silent(self) -> None:
        stream = io.StringIO()
        reporter = StageReporter(("扫描",), stream=stream, enabled=False)

        reporter.begin("扫描")
        reporter.complete("扫描")
        reporter.note("note")
        reporter.fail("boom")
        reporter.close()

        self.assertEqual(stream.getvalue(), "")

    def test_renderer_swallows_stream_errors(self) -> None:
        class BrokenStream:
            encoding = "utf-8"

            def isatty(self) -> bool:
                return False

            def write(self, text: str) -> int:
                raise RuntimeError("boom")

            def flush(self) -> None:
                raise RuntimeError("boom")

        reporter = StageReporter(("扫描",), stream=BrokenStream(), enabled=True)
        reporter.begin("扫描")
        reporter.complete("扫描")
        reporter.close()


class EvidenceRenderingTests(unittest.TestCase):
    def test_box_lines_share_one_width(self) -> None:
        lines = render_evidence(
            [
                ("契约", ".algocode/contract.json", "confidence 0.50"),
                ("任务", "task:abc", "ready"),
            ],
            unicode=True,
        )

        self.assertTrue(lines[0].startswith("┌"))
        self.assertTrue(lines[-1].startswith("└"))
        widths = {display_width(line) for line in lines}
        self.assertEqual(len(widths), 1, lines)

    def test_ascii_box_when_unicode_is_unavailable(self) -> None:
        lines = render_evidence([("契约", "contract.json", "confidence 0.50")], unicode=False)

        self.assertTrue(lines[0].startswith("+"))
        self.assertTrue(lines[-1].startswith("+"))
        self.assertNotIn("─", "".join(lines))


if __name__ == "__main__":
    unittest.main()
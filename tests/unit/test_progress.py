from __future__ import annotations

import io
import time
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


class DisplayWidthTests(unittest.TestCase):
    def test_wide_characters_count_as_two_cells(self) -> None:
        self.assertEqual(display_width("扫描"), 4)

    def test_ambiguous_glyphs_follow_the_terminal_model(self) -> None:
        self.assertEqual(display_width("──▶", ambiguous_wide=False), 3)
        self.assertEqual(display_width("──▶", ambiguous_wide=True), 6)


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


class StageRailOffsetTests(unittest.TestCase):
    def test_marker_offset_tracks_the_active_node(self) -> None:
        stages = ("扫描", "契约", "规格", "基线")
        for ambiguous_wide in (False, True):
            for label in stages:
                with self.subTest(ambiguous_wide=ambiguous_wide, label=label):
                    stream = io.StringIO()
                    reporter = StageReporter(
                        stages,
                        title="algocode · init",
                        stream=stream,
                        enabled=True,
                        color=False,
                        unicode=True,
                        ambiguous_wide=ambiguous_wide,
                    )
                    reporter.begin(label)
                    for previous in range(reporter._index_of(label)):
                        reporter._status[previous] = "done"

                    plain_rail, _styled, offset = reporter._rail()
                    prefix = plain_rail[: plain_rail.index(f"[{label}]")]

                    self.assertEqual(
                        offset,
                        display_width(prefix, ambiguous_wide=ambiguous_wide),
                        plain_rail,
                    )


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


class _TtyStream(io.StringIO):
    encoding = "utf-8"

    def isatty(self) -> bool:
        return True


def _live_reporter() -> tuple[StageReporter, _TtyStream]:
    stream = _TtyStream()
    reporter = StageReporter(
        ("扫描", "契约"),
        title="algocode · init",
        stream=stream,
        enabled=True,
        color=False,
        unicode=True,
    )
    # Drive the renderer directly: begin() would start the ticking thread.
    reporter._index = 0
    reporter._status[0] = "active"
    reporter._detail = "运行中"
    reporter._stage_started_at = time.perf_counter()
    return reporter, stream


class LiveBlockTests(unittest.TestCase):
    def test_the_block_leaves_the_cursor_on_its_last_line(self) -> None:
        reporter, stream = _live_reporter()

        reporter._render_locked()

        rendered = stream.getvalue()
        self.assertTrue(rendered.startswith("algocode · init"))
        self.assertTrue(rendered.endswith("\n"))
        self.assertIn("\n", rendered.rstrip("\n"))

    def test_erasing_climbs_one_line_less_than_the_block(self) -> None:
        reporter, stream = _live_reporter()
        reporter._render_locked()
        stream.truncate(0)
        stream.seek(0)

        reporter._erase_locked()

        self.assertEqual(stream.getvalue(), "\x1b[2A\r\x1b[0J")

    def test_the_tick_repaints_the_dynamic_block(self) -> None:
        reporter, stream = _live_reporter()
        reporter._render_locked()
        stream.truncate(0)
        stream.seek(0)

        reporter._refresh_detail_locked()

        rendered = stream.getvalue()
        self.assertTrue(rendered.startswith("\x1b[2A\r\x1b[0J"))
        self.assertIn("──▶", rendered)
        self.assertTrue(rendered.endswith("\n"))

    def test_arrow_aligns_with_the_active_stage(self) -> None:
        stages = ("扫描", "契约", "规格", "基线")
        for ambiguous_wide in (False, True):
            for label in stages:
                with self.subTest(ambiguous_wide=ambiguous_wide, label=label):
                    stream = _TtyStream()
                    reporter = StageReporter(
                        stages,
                        title="algocode · init",
                        stream=stream,
                        enabled=True,
                        color=False,
                        unicode=True,
                        ambiguous_wide=ambiguous_wide,
                    )
                    reporter._index = reporter._index_of(label)
                    reporter._status[reporter._index] = "active"
                    for previous in range(reporter._index):
                        reporter._status[previous] = "done"
                    reporter._detail = "运行中"
                    reporter._stage_started_at = time.perf_counter()

                    rail, detail = reporter._build_lines()
                    prefix = rail[: rail.index(f"[{label}]")]
                    expected = display_width(
                        prefix,
                        ambiguous_wide=ambiguous_wide,
                    )
                    self.assertTrue(detail.startswith(" " * expected + "▲"))

    def test_completion_prints_a_permanent_line_then_redraws_the_rail(self) -> None:
        reporter, stream = _live_reporter()
        reporter._render_locked()
        stream.truncate(0)
        stream.seek(0)

        reporter.complete("扫描", "python")

        rendered = stream.getvalue()
        payload = rendered.split("\x1b[0J", 1)[-1]
        lines = payload.rstrip("\n").split("\n")
        self.assertEqual(len(lines), 2)
        self.assertNotIn("扫描", lines[0])
        self.assertIn("契约", lines[0])
        self.assertIn("algocode · init:  扫描 ✔", lines[1])

    def test_next_stage_is_first_on_rail_with_completions_below(self) -> None:
        reporter, _stream = _live_reporter()
        reporter.complete("扫描", "python")
        reporter._index = 1
        reporter._status[1] = "active"
        reporter._detail = "生成契约"
        reporter._stage_started_at = time.perf_counter()

        rail, detail, completion = reporter._build_lines()

        self.assertIn("[契约]", rail)
        self.assertNotIn("扫描", rail)
        self.assertIn("生成契约", detail)
        self.assertIn("algocode · init:  扫描 ✔", completion)


    def test_close_removes_the_final_dynamic_rail(self) -> None:
        reporter, stream = _live_reporter()
        reporter.complete("扫描", "python")
        stream.truncate(0)
        stream.seek(0)

        reporter.close()

        rendered = stream.getvalue()
        self.assertTrue(rendered.startswith("\x1b[2A\r\x1b[0J"))
        self.assertIn("algocode · init:  扫描 ✔", rendered)
        self.assertNotIn("[契约]", rendered)


if __name__ == "__main__":
    unittest.main()

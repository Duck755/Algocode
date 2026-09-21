from __future__ import annotations

import io
import unittest
from datetime import UTC, datetime, timedelta

from algocode.cli.live_progress import (
    LiveProgress,
    action_line,
    analyze_events,
    fit_line,
    phase_label,
    phase_line,
    tick_line,
    tool_label,
    tool_status_label,
    transition_line,
)
from algocode.domain.events import EventEnvelope, EventType

BASE = datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC)


def _event(seq: int, kind: EventType, offset: float, **payload: object) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{seq}",
        aggregate_id="task_1",
        seq=seq,
        type=kind,
        timestamp=BASE + timedelta(seconds=offset),
        payload=payload,
    )


def _analysis_events() -> list[EventEnvelope]:
    return [
        _event(1, EventType.TASK_PHASE_CHANGED, 0, current_phase="analyze", status="running"),
        _event(2, EventType.AGENT_TURN_STARTED, 1, phase="analyze", turn=1),
        _event(
            3,
            EventType.TOOL_CALL_STARTED,
            2,
            phase="analyze",
            tool_call_id="t1",
            name="read_required_files",
        ),
        _event(
            4,
            EventType.TOOL_CALL_COMPLETED,
            14,
            phase="analyze",
            tool_call_id="t1",
            name="read_required_files",
            status="success",
        ),
        _event(5, EventType.AGENT_TURN_STARTED, 15, phase="analyze", turn=2),
        _event(
            6,
            EventType.TOOL_CALL_STARTED,
            16,
            phase="analyze",
            tool_call_id="t2",
            name="search_code",
        ),
    ]


def _transition_events() -> list[EventEnvelope]:
    return [
        _event(30, EventType.TASK_PHASE_CHANGED, 100, current_phase="compare", status="running"),
        _event(
            31,
            EventType.AGENT_PHASE_REENTERED,
            101,
            from_phase="compare",
            to_phase="implement",
            reason="candidate has valid positive evidence",
            candidate_id="cand_1",
            iteration=1,
        ),
        _event(32, EventType.TASK_PHASE_CHANGED, 102, current_phase="implement", status="running"),
    ]


def _full_events() -> list[EventEnvelope]:
    return [
        *_analysis_events(),
        _event(7, EventType.TASK_PHASE_CHANGED, 64, current_phase="baseline", status="running"),
        _event(
            8,
            EventType.TOOL_CALL_STARTED,
            65,
            phase="baseline",
            tool_call_id="t3",
            name="build",
        ),
        _event(
            9,
            EventType.TOOL_CALL_COMPLETED,
            70,
            phase="baseline",
            tool_call_id="t3",
            name="build",
            status="error",
        ),
    ]


class _Stream(io.StringIO):
    encoding = "utf-8"

    def __init__(self, *, tty: bool = False) -> None:
        super().__init__()
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


class LabelTests(unittest.TestCase):
    def test_phase_labels_are_english(self) -> None:
        self.assertEqual(phase_label("analyze"), "Analyze")
        self.assertEqual(phase_label("generate_candidate"), "Generate Candidate")
        self.assertEqual(phase_label("report"), "Report")

    def test_unknown_phase_falls_back_to_the_raw_name(self) -> None:
        self.assertEqual(phase_label("future_phase"), "future_phase")
        self.assertEqual(phase_label(None), "Unknown Phase")

    def test_tool_labels_are_english(self) -> None:
        self.assertEqual(tool_label("read_required_files"), "Read Required Files")
        self.assertEqual(tool_label("run_correctness"), "Run Correctness")
        self.assertEqual(tool_label("unknown_tool"), "unknown_tool")
        self.assertEqual(tool_label(None), "Tool")

    def test_tool_status_labels(self) -> None:
        self.assertEqual(tool_status_label("success"), "success")
        self.assertEqual(tool_status_label("error"), "failed")
        self.assertEqual(tool_status_label("interrupted"), "failed")
        self.assertEqual(tool_status_label(None), "failed")


class AnalyzeEventsTests(unittest.TestCase):
    def test_tracks_phase_turn_and_tool_ordinals(self) -> None:
        snapshot = analyze_events(_full_events())

        self.assertEqual(snapshot.current, "baseline")
        self.assertEqual([stat.name for stat in snapshot.phases], ["analyze", "baseline"])
        analyze = snapshot.stat("analyze")
        assert analyze is not None
        self.assertEqual(analyze.turn, 2)
        self.assertEqual(analyze.tool_calls, 2)
        self.assertEqual(analyze.started_at, BASE)
        baseline = snapshot.stat("baseline")
        assert baseline is not None
        self.assertEqual(baseline.tool_calls, 1)
        self.assertEqual(baseline.turn, None)

    def test_records_tool_durations_and_the_active_action(self) -> None:
        snapshot = analyze_events(_full_events())

        finished = snapshot.actions[0]
        self.assertEqual(finished.ordinal, 1)
        self.assertEqual(finished.seconds, 12.0)
        self.assertEqual(snapshot.actions[1].ordinal, 2)
        self.assertIsNone(snapshot.actions[1].seconds)
        active = snapshot.active
        assert active is not None
        self.assertEqual(active.name, "search_code")

    def test_empty_log_produces_an_empty_snapshot(self) -> None:
        snapshot = analyze_events([])

        self.assertEqual(snapshot.phases, [])
        self.assertIsNone(snapshot.current)
        self.assertIsNone(snapshot.active)


class LineFormatTests(unittest.TestCase):
    def test_ticking_line_names_the_running_tool(self) -> None:
        snapshot = analyze_events(_analysis_events())

        line = tick_line(snapshot, now=BASE + timedelta(seconds=28))

        self.assertEqual(
            line,
            "[algocode] Analyze | 1/10 | Round 2 | Running Search Code (12s) | Tools 2 | 28s",
        )

    def test_ticking_line_says_thinking_without_an_active_tool(self) -> None:
        snapshot = analyze_events(_analysis_events()[:2])

        line = tick_line(snapshot, now=BASE + timedelta(seconds=5))

        self.assertIn("Thinking", line)
        self.assertNotIn("Running", line)

    def test_frozen_action_line_reports_success(self) -> None:
        snapshot = analyze_events(_full_events())

        line = action_line(snapshot.actions[0], marker="\u2714")

        self.assertEqual(
            line,
            "[algocode] Analyze | 1/10 | Round 1 | Read Required Files success | Tool 1 | 12s \u2714",  # noqa: E501
        )

    def test_frozen_action_line_reports_failure(self) -> None:
        snapshot = analyze_events(_full_events())

        line = action_line(snapshot.actions[2], marker="\u2716")

        self.assertEqual(line, "[algocode] Baseline | 2/10 | Build failed | Tool 1 | 5.0s \u2716")

    def test_phase_summary_line_counts_turns_and_tools(self) -> None:
        snapshot = analyze_events(_analysis_events())
        analyze = snapshot.stat("analyze")
        assert analyze is not None

        line = phase_line(analyze, elapsed=244.0, marker="\u2714")

        self.assertEqual(
            line,
            "[algocode] Analyze | 1/10 | Completed · 2 reasoning turns · 2 tool calls | 4m04s \u2714",  # noqa: E501
        )

    def test_transition_line_explains_a_back_jump(self) -> None:
        transition = analyze_events(_transition_events()).transitions[0]

        line = transition_line(transition, marker="!", title="algocode")

        self.assertIn("Phase fallback", line)
        self.assertIn("Compare → Implement", line)
        self.assertIn("candidate has valid positive evidence", line)
        self.assertTrue(line.endswith("!"))


class FitLineTests(unittest.TestCase):
    def test_short_lines_are_untouched(self) -> None:
        self.assertEqual(fit_line("abc", 10), "abc")

    def test_long_lines_are_trimmed_with_an_ellipsis(self) -> None:
        self.assertEqual(fit_line("abcdef", 4), "abc…")

    def test_wide_characters_count_as_two_cells(self) -> None:
        self.assertEqual(fit_line("中文中文", 6), "中文…")


class LiveProgressTests(unittest.TestCase):
    def test_plain_stream_prints_only_frozen_lines(self) -> None:
        stream = _Stream()
        live = LiveProgress(
            load_events=_full_events,
            stream=stream,
            enabled=True,
            color=False,
        )

        live.close(ok=True)

        lines = stream.getvalue().splitlines()
        self.assertEqual(
            lines,
            [
                "[algocode] Analyze | 1/10 | Round 1 | Read Required Files success | Tool 1 | 12s \u2714",  # noqa: E501
                "[algocode] Analyze | 1/10 | Completed · 2 reasoning turns · 2 tool calls | 1m04s \u2714",  # noqa: E501
                "[algocode] Baseline | 2/10 | Build failed | Tool 1 | 5.0s \u2716",
                "[algocode] Baseline | 2/10 | Completed · 0 reasoning turns · 1 tool calls | 6.0s \u2714",  # noqa: E501
            ],
        )
        self.assertNotIn("\x1b", stream.getvalue())

    def test_failed_phase_is_marked_when_the_run_failed(self) -> None:
        stream = _Stream()
        live = LiveProgress(load_events=_analysis_events, stream=stream, color=False)

        live.close(ok=False)

        self.assertTrue(stream.getvalue().splitlines()[-1].endswith("\u2716"))

    def test_disabled_reporter_is_silent(self) -> None:
        stream = _Stream()
        live = LiveProgress(load_events=_full_events, stream=stream, enabled=False)

        live.start()
        live.close(ok=True)

        self.assertEqual(stream.getvalue(), "")

    def test_interactive_stream_refreshes_one_line_before_freezing(self) -> None:
        stream = _Stream(tty=True)
        live = LiveProgress(
            load_events=_analysis_events,
            stream=stream,
            enabled=True,
            color=False,
        )

        live.tick_once()

        text = stream.getvalue()
        self.assertIn("\r\x1b[2K", text)
        self.assertIn("Running Search Code", text)
        self.assertIn("\u2714", text)
        self.assertFalse(text.endswith("\n"))
        self.assertIn("\u2714", text.rsplit("\r\x1b[2K", 1)[0])

        live.close(ok=True)
        self.assertTrue(stream.getvalue().endswith("\n"))

    def test_phase_reentry_is_printed_before_the_second_implement(self) -> None:
        stream = _Stream()
        live = LiveProgress(load_events=_transition_events, stream=stream, color=False)

        live.close(ok=True)

        lines = stream.getvalue().splitlines()
        self.assertTrue(any("Phase fallback" in line for line in lines))
        self.assertTrue(any("Compare → Implement" in line for line in lines))

    def test_ascii_fallback_replaces_the_check_marks(self) -> None:
        stream = io.StringIO()
        live = LiveProgress(load_events=_analysis_events, stream=stream, enabled=True)

        live.close(ok=True)

        text = stream.getvalue()
        self.assertNotIn("\u2714", text)
        self.assertIn("success", text)
        self.assertIn(" ok", text)

    def test_start_ignores_history_from_earlier_runs(self) -> None:
        recorded = _analysis_events()
        later = [
            _event(20, EventType.TASK_PHASE_CHANGED, 200, current_phase="plan", status="running"),
            _event(
                21,
                EventType.TOOL_CALL_STARTED,
                201,
                phase="plan",
                tool_call_id="t9",
                name="build",
            ),
            _event(
                22,
                EventType.TOOL_CALL_COMPLETED,
                205,
                phase="plan",
                tool_call_id="t9",
                name="build",
                status="success",
            ),
        ]
        stream = _Stream()
        live = LiveProgress(load_events=lambda: list(recorded), stream=stream, color=False)

        live.start()
        recorded.extend(later)
        live.close(ok=True)

        text = stream.getvalue()
        self.assertIn("Plan | 3/10", text)
        self.assertNotIn("Analyze | 1/10", text)
        self.assertNotIn("Baseline | 2/10", text)

    def test_stream_errors_never_propagate(self) -> None:
        class BrokenStream:
            encoding = "utf-8"

            def isatty(self) -> bool:
                return False

            def write(self, text: str) -> int:
                raise RuntimeError("boom")

            def flush(self) -> None:
                raise RuntimeError("boom")

        live = LiveProgress(load_events=_full_events, stream=BrokenStream(), enabled=True)

        live.start()
        live.tick_once()
        live.close(ok=True)

    def test_loader_errors_never_propagate(self) -> None:
        def boom() -> list[EventEnvelope]:
            raise RuntimeError("boom")

        stream = _Stream()
        live = LiveProgress(load_events=boom, stream=stream, enabled=True)

        live.tick_once()
        live.close(ok=True)

        self.assertEqual(stream.getvalue(), "")


if __name__ == "__main__":
    unittest.main()

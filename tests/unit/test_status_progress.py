from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from algocode.cli.commands.status import _build_progress, _progress_line
from algocode.domain.events import EventEnvelope, EventType


START = datetime(2026, 1, 1, tzinfo=UTC)


def event(seq: int, event_type: EventType, payload: dict, seconds: int) -> EventEnvelope:
    return EventEnvelope(
        id=f"evt_{seq}",
        aggregate_id="task_1",
        seq=seq,
        type=event_type,
        timestamp=START + timedelta(seconds=seconds),
        payload=payload,
    )


class StatusProgressTests(unittest.TestCase):
    def test_progress_reports_turn_active_tool_and_last_completed_tool(self) -> None:
        events = (
            event(
                1,
                EventType.TASK_PHASE_CHANGED,
                {"current_phase": "implement", "status": "running"},
                0,
            ),
            event(2, EventType.AGENT_TURN_STARTED, {"phase": "implement", "turn": 3}, 1),
            event(
                3,
                EventType.TOOL_CALL_STARTED,
                {
                    "phase": "implement",
                    "tool_call_id": "call_1",
                    "name": "read_file",
                },
                2,
            ),
            event(
                4,
                EventType.TOOL_CALL_COMPLETED,
                {
                    "phase": "implement",
                    "tool_call_id": "call_1",
                    "name": "read_file",
                    "status": "success",
                    "summary": "read test.py",
                },
                4,
            ),
            event(
                5,
                EventType.TOOL_CALL_STARTED,
                {
                    "phase": "implement",
                    "tool_call_id": "call_2",
                    "name": "edit_file",
                },
                6,
            ),
        )

        progress = _build_progress(
            events,
            "implement",
            now=START + timedelta(seconds=10),
        )

        self.assertEqual(progress["turn"], 3)
        self.assertEqual(progress["toolCalls"], 2)
        self.assertEqual(progress["phaseElapsedSeconds"], 10.0)
        self.assertEqual(progress["activeTool"]["name"], "edit_file")
        self.assertEqual(progress["activeTool"]["elapsedSeconds"], 4.0)
        self.assertEqual(progress["lastTool"]["name"], "read_file")
        self.assertEqual(progress["lastTool"]["status"], "success")
        self.assertIn("tool=edit_file", _progress_line(progress))

    def test_progress_handles_task_without_events(self) -> None:
        progress = _build_progress((), "analyze", now=START)

        self.assertEqual(progress["phase"], "analyze")
        self.assertIsNone(progress["turn"])
        self.assertEqual(progress["toolCalls"], 0)
        self.assertEqual(progress["lastEventSummary"], "waiting")


if __name__ == "__main__":
    unittest.main()

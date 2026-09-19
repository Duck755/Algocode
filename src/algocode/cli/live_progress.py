"""Polling log-line progress for long-running agent commands.

While ``optimize`` runs, the reporter keeps a single line ticking in place and
then freezes it into a permanent log line with a trailing check mark. It reads
the durable event log instead of hooking into the runtime, so the CLI narration
and the VS Code panel are derived from exactly the same facts.

Rendering is best-effort: every failure inside the poller is swallowed so that
progress can never break the command it narrates.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
import threading
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TextIO

from algocode.cli.progress import display_width, format_duration, supports_unicode
from algocode.domain.events import EventEnvelope, EventType

TITLE = "algocode"

PHASE_LABELS: Mapping[str, str] = {
    "create": "建任务",
    "analyze": "分析",
    "baseline": "基线",
    "plan": "方案",
    "generate_candidate": "建候选",
    "implement": "实现",
    "verify": "校验",
    "benchmark": "基准",
    "compare": "对比",
    "decide": "决策",
    "report": "报告",
}

TOOL_LABELS: Mapping[str, str] = {
    "list_files": "列目录",
    "read_file": "读取文件",
    "read_required_files": "读取必需文件",
    "write_file": "写入文件",
    "edit_file": "编辑文件",
    "search_code": "搜索代码",
    "read_resource": "读取资源",
    "get_task_state": "读取任务状态",
    "get_candidate_diff": "查看候选改动",
    "create_candidate": "创建候选",
    "apply_patch": "应用补丁",
    "build": "编译",
    "run_correctness": "运行正确性测试",
    "run_candidate_check": "候选自检",
    "run_benchmark": "运行基准",
    "run_contract": "运行契约测试",
    "submit_phase_result": "提交阶段结果",
    "submit_optimization_plan": "提交优化方案",
    "run_shell": "执行命令",
}

OPTIMIZE_PHASES: tuple[str, ...] = (
    "analyze",
    "baseline",
    "plan",
    "generate_candidate",
    "implement",
    "verify",
    "benchmark",
    "compare",
    "decide",
    "report",
)

_UNICODE_GLYPHS: Mapping[str, str] = {"done": "✔", "failed": "✖"}
_ASCII_GLYPHS: Mapping[str, str] = {"done": "ok", "failed": "x"}

_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_GREEN = "\x1b[32m"
_RED = "\x1b[31m"

_TOOL_OK_STATUSES = {"success", "ok", "completed", "passed"}


def phase_label(name: str | None) -> str:
    """Chinese label for a task phase name."""
    if not name:
        return "未知阶段"
    return PHASE_LABELS.get(name, name)


def tool_label(name: str | None) -> str:
    """Chinese label for a tool name."""
    if not name:
        return "工具"
    return TOOL_LABELS.get(name, name)


def tool_status_label(status: str | None) -> str:
    """Chinese label for a tool result status."""
    return "成功" if (status or "").lower() in _TOOL_OK_STATUSES else "失败"


def tool_succeeded(status: str | None) -> bool:
    return (status or "").lower() in _TOOL_OK_STATUSES


def glyphs_for(stream: TextIO | None = None) -> Mapping[str, str]:
    """Pick the marker glyph set this stream can actually encode."""
    return _UNICODE_GLYPHS if supports_unicode(stream) else _ASCII_GLYPHS


@dataclass(slots=True)
class Action:
    """One tool call observed in the durable event log."""

    tool_call_id: str
    name: str
    phase: str
    turn: int | None
    ordinal: int
    started_at: datetime
    completed_at: datetime | None = None
    status: str = ""
    summary: str = ""

    @property
    def seconds(self) -> float | None:
        if self.completed_at is None:
            return None
        return max(0.0, (self.completed_at - self.started_at).total_seconds())


@dataclass(slots=True)
class PhaseStat:
    """Accumulated facts about one phase."""

    name: str
    started_at: datetime | None = None
    last_at: datetime | None = None
    turn: int | None = None
    tool_calls: int = 0


@dataclass(slots=True)
class _Freeze:
    """One log line waiting to be printed, ordered by when its work ended."""

    at: datetime
    order: int
    text: str
    ok: bool
    tool_id: str | None = None
    phase: str | None = None


@dataclass(slots=True)
class Snapshot:
    """Everything the renderer needs, derived from one event-log read."""

    phases: list[PhaseStat] = field(default_factory=list)
    current: str | None = None
    actions: list[Action] = field(default_factory=list)

    def stat(self, name: str | None) -> PhaseStat | None:
        if name is None:
            return None
        return next((item for item in self.phases if item.name == name), None)

    @property
    def active(self) -> Action | None:
        return next(
            (action for action in reversed(self.actions) if action.completed_at is None),
            None,
        )


def analyze_events(events: Iterable[EventEnvelope]) -> Snapshot:
    """Fold the durable event log into a renderable snapshot."""

    snapshot = Snapshot()
    by_id: dict[str, Action] = {}
    phase_by_name: dict[str, PhaseStat] = {}
    current: str | None = None
    for event in sorted(events, key=lambda item: item.seq):
        payload = event.payload or {}
        if event.type is EventType.TASK_PHASE_CHANGED:
            name = str(payload.get("current_phase") or current or "")
            if not name:
                continue
            current = name
            stat = _phase_stat(snapshot, phase_by_name, name)
            if stat.started_at is None:
                stat.started_at = event.timestamp
            stat.last_at = event.timestamp
            continue
        name = str(payload.get("phase") or current or "")
        if not name:
            continue
        stat = _phase_stat(snapshot, phase_by_name, name)
        if stat.started_at is None:
            stat.started_at = event.timestamp
        stat.last_at = event.timestamp
        if event.type is EventType.AGENT_TURN_STARTED:
            turn = payload.get("turn")
            if isinstance(turn, int):
                stat.turn = turn
        elif event.type is EventType.TOOL_CALL_STARTED:
            stat.tool_calls += 1
            action = Action(
                tool_call_id=str(payload.get("tool_call_id") or f"tool-{event.seq}"),
                name=str(payload.get("name") or ""),
                phase=name,
                turn=stat.turn,
                ordinal=stat.tool_calls,
                started_at=event.timestamp,
            )
            snapshot.actions.append(action)
            by_id[action.tool_call_id] = action
        elif event.type is EventType.TOOL_CALL_COMPLETED:
            action = by_id.get(str(payload.get("tool_call_id") or ""))
            if action is None:
                continue
            action.completed_at = event.timestamp
            action.status = str(payload.get("status") or "")
            action.summary = str(payload.get("summary") or "")
    snapshot.current = current
    return snapshot


def _phase_stat(
    snapshot: Snapshot,
    phase_by_name: dict[str, PhaseStat],
    name: str,
) -> PhaseStat:
    stat = phase_by_name.get(name)
    if stat is None:
        stat = PhaseStat(name=name)
        phase_by_name[name] = stat
        snapshot.phases.append(stat)
    return stat


def phase_ordinal(
    name: str | None,
    phases: Sequence[str] = OPTIMIZE_PHASES,
) -> tuple[int, int] | None:
    """One-based position of ``name`` inside the phase rail, when known."""

    if not name:
        return None
    try:
        return phases.index(name) + 1, len(phases)
    except ValueError:
        return None


def _join(parts: Sequence[str], title: str = TITLE) -> str:
    return f"[{title}] " + " | ".join(part for part in parts if part)


def _phase_parts(
    name: str | None,
    turn: int | None,
    phases: Sequence[str],
) -> list[str]:
    parts = [phase_label(name)]
    ordinal = phase_ordinal(name, phases)
    if ordinal is not None:
        parts.append(f"{ordinal[0]}/{ordinal[1]}")
    if turn is not None:
        parts.append(f"第 {turn} 轮")
    return parts


def elapsed_since(start: datetime | None, now: datetime) -> float | None:
    if start is None:
        return None
    return max(0.0, (now - start).total_seconds())


def tick_line(
    snapshot: Snapshot,
    *,
    phases: Sequence[str] = OPTIMIZE_PHASES,
    now: datetime | None = None,
    title: str = TITLE,
) -> str:
    """The single line that keeps ticking while an action runs."""

    current = datetime.now(UTC) if now is None else now
    stat = snapshot.stat(snapshot.current)
    parts = _phase_parts(snapshot.current, stat.turn if stat else None, phases)
    active = snapshot.active
    if active is not None:
        seconds = max(0.0, (current - active.started_at).total_seconds())
        parts.append(f"运行中 {tool_label(active.name)} ({format_duration(seconds)})")
    else:
        parts.append("思考中")
    parts.append(f"工具 {stat.tool_calls if stat else 0}")
    elapsed = elapsed_since(stat.started_at if stat else None, current)
    if elapsed is not None:
        parts.append(format_duration(elapsed))
    return _join(parts, title=title)


def action_line(
    action: Action,
    *,
    phases: Sequence[str] = OPTIMIZE_PHASES,
    marker: str = "",
    title: str = TITLE,
) -> str:
    """A frozen log line for one finished tool call."""

    parts = _phase_parts(action.phase, action.turn, phases)
    parts.append(f"{tool_label(action.name)} {tool_status_label(action.status)}")
    parts.append(f"工具 {action.ordinal}")
    seconds = action.seconds
    if seconds is not None:
        parts.append(format_duration(seconds))
    text = _join(parts, title=title)
    return f"{text} {marker}" if marker else text


def phase_line(
    stat: PhaseStat,
    *,
    phases: Sequence[str] = OPTIMIZE_PHASES,
    elapsed: float | None = None,
    marker: str = "",
    title: str = TITLE,
) -> str:
    """A frozen log line summarising one finished phase."""

    parts = _phase_parts(stat.name, None, phases)
    parts.append(
        f"完成 · {stat.turn or 0} 轮推理 · {stat.tool_calls} 次工具调用"
    )
    if elapsed is not None:
        parts.append(format_duration(elapsed))
    text = _join(parts, title=title)
    return f"{text} {marker}" if marker else text


def _is_tty(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def fit_line(text: str, width: int) -> str:
    """Trim a line to one terminal row, counting wide characters as two cells."""

    if width < 4 or display_width(text) <= width:
        return text
    out: list[str] = []
    used = 0
    for char in text:
        cell = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if used + cell > width - 1:
            break
        out.append(char)
        used += cell
    return "".join(out) + "…"


class LiveProgress:
    """Poll the event log and narrate the run as streaming log lines."""

    def __init__(
        self,
        *,
        load_events: Callable[[], Sequence[EventEnvelope]],
        phases: Sequence[str] = OPTIMIZE_PHASES,
        stream: TextIO | None = None,
        enabled: bool = True,
        color: bool | None = None,
        interval: float = 0.5,
        title: str = TITLE,
    ) -> None:
        self._load_events = load_events
        self._phases = tuple(phases)
        self._stream = stream if stream is not None else sys.stderr
        self._title = title
        self._interval = interval
        self._enabled = bool(enabled)
        self._interactive = self._enabled and _is_tty(self._stream)
        self._color = self._interactive if color is None else bool(color) and self._interactive
        self._glyphs = glyphs_for(self._stream)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._drawn = False
        self._start_seq: int | None = None
        self._frozen_tools: set[str] = set()
        self._frozen_phases: set[str] = set()

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        if not self._enabled or self._thread is not None:
            return
        self._capture_baseline()
        self._thread = threading.Thread(
            target=self._loop,
            name="algocode-live-progress",
            daemon=True,
        )
        self._thread.start()

    def tick_once(self) -> None:
        """Render one refresh cycle; useful for embedding and for tests."""

        if not self._enabled:
            return
        try:
            self._tick()
        except Exception:  # noqa: BLE001
            return

    def close(self, *, ok: bool = True, note: str = "") -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None
        if not self._enabled:
            return
        try:
            self._tick(final=True, ok=ok)
            if note:
                self._emit(note)
        except Exception:  # noqa: BLE001
            pass
        finally:
            self._erase()
            self._flush()

    def _capture_baseline(self) -> None:
        """Remember where this run starts so retry history stays out of the log."""

        try:
            events = self._load_events()
        except Exception:  # noqa: BLE001
            return
        self._start_seq = max((event.seq for event in events), default=0)

    def _events(self) -> Sequence[EventEnvelope]:
        events = self._load_events()
        if self._start_seq is None:
            return events
        return [event for event in events if event.seq > self._start_seq]

    def _loop(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._tick()
            except Exception:  # noqa: BLE001
                continue

    # -- rendering ---------------------------------------------------------

    def _tick(self, *, final: bool = False, ok: bool = True) -> None:
        with self._lock:
            snapshot = analyze_events(self._events())
            for item in self._pending(snapshot, final=final, ok=ok):
                if item.tool_id is not None:
                    self._frozen_tools.add(item.tool_id)
                if item.phase is not None:
                    self._frozen_phases.add(item.phase)
                self._emit(item.text, ok=item.ok)
            if final:
                self._erase()
            else:
                self._refresh(tick_line(snapshot, phases=self._phases, title=self._title))

    def _pending(self, snapshot: Snapshot, *, final: bool, ok: bool) -> list[_Freeze]:
        """Frozen log lines, ordered by the moment the narrated work ended."""

        entries: list[_Freeze] = []
        for action in snapshot.actions:
            if action.completed_at is None or action.tool_call_id in self._frozen_tools:
                continue
            succeeded = tool_succeeded(action.status)
            entries.append(
                _Freeze(
                    at=action.completed_at,
                    order=0,
                    tool_id=action.tool_call_id,
                    ok=succeeded,
                    text=action_line(
                        action,
                        phases=self._phases,
                        marker=self._glyphs["done" if succeeded else "failed"],
                        title=self._title,
                    ),
                )
            )
        for index, stat in enumerate(snapshot.phases):
            if stat.name in self._frozen_phases:
                continue
            is_last = index == len(snapshot.phases) - 1
            if is_last and not final:
                continue
            following = snapshot.phases[index + 1] if not is_last else None
            if following is not None and following.started_at is not None:
                end = following.started_at
                succeeded = True
            else:
                end = stat.last_at
                succeeded = ok
            elapsed = (
                max(0.0, (end - stat.started_at).total_seconds())
                if end is not None and stat.started_at is not None
                else None
            )
            entries.append(
                _Freeze(
                    at=end or stat.started_at or datetime.now(UTC),
                    order=1,
                    phase=stat.name,
                    ok=succeeded,
                    text=phase_line(
                        stat,
                        phases=self._phases,
                        elapsed=elapsed,
                        marker=self._glyphs["done" if succeeded else "failed"],
                        title=self._title,
                    ),
                )
            )
        entries.sort(key=lambda item: (item.at, item.order))
        return entries

    def _emit(self, text: str, *, ok: bool | None = None) -> None:
        if not self._enabled:
            return
        if self._interactive:
            self._erase()
        self._write(f"{self._styled(text, ok)}\n")
        self._flush()

    def _refresh(self, text: str) -> None:
        if not self._interactive:
            return
        width = max(20, shutil.get_terminal_size((100, 24)).columns - 1)
        line = fit_line(text, width)
        self._write(f"\r\x1b[2K{self._paint(line, _DIM)}")
        self._flush()
        self._drawn = True

    def _erase(self) -> None:
        if not self._interactive or not self._drawn:
            return
        self._write("\r\x1b[2K")
        self._flush()
        self._drawn = False

    def _styled(self, text: str, ok: bool | None) -> str:
        if ok is None or not self._color:
            return text
        marker = self._glyphs["done"] if ok else self._glyphs["failed"]
        if not marker or not text.endswith(marker):
            return text
        return text[: -len(marker)] + self._paint(marker, _GREEN if ok else _RED)

    def _paint(self, text: str, code: str) -> str:
        if not self._color:
            return text
        return f"{code}{text}{_RESET}"

    def _write(self, text: str) -> None:
        try:
            self._stream.write(text)
        except Exception:  # noqa: BLE001
            self._enabled = False

    def _flush(self) -> None:
        try:
            self._stream.flush()
        except Exception:  # noqa: BLE001
            self._enabled = False


def poll_events(event_store: object, task_id: str) -> Callable[[], Sequence[EventEnvelope]]:
    """Build a thread-safe loader that re-reads one task's event log."""

    def load() -> Sequence[EventEnvelope]:
        return asyncio.run(event_store.read(task_id))  # type: ignore[attr-defined]

    return load


__all__ = [
    "OPTIMIZE_PHASES",
    "PHASE_LABELS",
    "TOOL_LABELS",
    "Action",
    "LiveProgress",
    "PhaseStat",
    "Snapshot",
    "action_line",
    "analyze_events",
    "fit_line",
    "glyphs_for",
    "phase_label",
    "phase_line",
    "phase_ordinal",
    "poll_events",
    "tick_line",
    "tool_label",
    "tool_status_label",
    "tool_succeeded",
]
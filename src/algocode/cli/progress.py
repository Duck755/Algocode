"""Live stage progress rendering for long-running CLI commands.

On a TTY the reporter keeps a two-line block on stderr: a stage rail and a
detail line that ticks elapsed time, so a multi-minute model call never looks
hung. Anywhere else it degrades to plain single-line records.

Rendering is deliberately best-effort. Every public method swallows its own
errors: progress must never break the command it narrates.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import unicodedata
from collections.abc import Sequence
from typing import TextIO

_RESET = "\x1b[0m"
_DIM = "\x1b[2m"
_BOLD = "\x1b[1m"
_GREEN = "\x1b[32m"
_CYAN = "\x1b[36m"
_RED = "\x1b[31m"

_PENDING = "pending"
_ACTIVE = "active"
_DONE = "done"
_FAILED = "failed"

_UNICODE_GLYPHS = {
    "arrow": " ──▶ ",
    "done": "✔",
    "failed": "✖",
    "active": "▲",
    "note": "!",
}
_ASCII_GLYPHS = {
    "arrow": " --> ",
    "done": " ok",
    "failed": " x",
    "active": ">",
    "note": "!",
}


def format_duration(seconds: float) -> str:
    """Render a short human duration: ``240ms``, ``3.2s``, ``1m04s``."""
    if seconds < 1:
        return f"{max(0.0, seconds) * 1000:.0f}ms"
    if seconds < 10:
        return f"{seconds:.1f}s"
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes, remainder = divmod(int(seconds), 60)
    return f"{minutes}m{remainder:02d}s"


def _is_tty(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError):
        return False


def _supports_unicode(stream: TextIO) -> bool:
    encoding = getattr(stream, "encoding", None) or "ascii"
    try:
        "──▶✔✖▲".encode(encoding)
    except (UnicodeEncodeError, LookupError):
        return False
    return True


def supports_unicode(stream: TextIO | None = None) -> bool:
    """Return True when the stream's encoding can render the rail glyphs."""
    return _supports_unicode(stream if stream is not None else sys.stdout)


def display_width(text: str, *, ambiguous_wide: bool = False) -> int:
    """Terminal cell width, counting East Asian wide characters as two.

    ``ambiguous_wide`` also counts East Asian *ambiguous* characters (box
    drawing, arrows, the middle dot) as two cells, which is how CJK terminal
    fonts render them. The rail separator and the active marker are built from
    such characters, so the wrong width model misplaces the marker.
    """
    wide = {"W", "F", "A"} if ambiguous_wide else {"W", "F"}
    return sum(2 if unicodedata.east_asian_width(char) in wide else 1 for char in text)


def _infer_ambiguous_wide() -> bool:
    """Return whether East Asian ambiguous glyphs occupy two terminal cells.

    CJK console fonts on Windows draw box drawing, arrow, and middle-dot
    glyphs at double width, while most Linux terminals keep them narrow.
    ``ALGOCODE_AMBIGUOUS_WIDTH=wide|narrow`` overrides the guess.
    """
    override = os.environ.get("ALGOCODE_AMBIGUOUS_WIDTH", "").strip().lower()
    if override in {"wide", "2", "full"}:
        return True
    if override in {"narrow", "1", "half"}:
        return False
    return sys.platform == "win32"


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - display_width(text))


def render_evidence(
    rows: Sequence[tuple[str, str, str]],
    *,
    title: str = "Evidence Chain",
    unicode: bool | None = None,
    indent: str = "  ",
) -> list[str]:
    """Render aligned evidence rows as a boxed block.

    Every returned line has the same terminal cell width, including the frame.
    Wide (East Asian) characters are measured with :func:`display_width` so the
    right border stays straight even in mixed CJK/Latin rows.
    """
    if not rows:
        return []
    wide = supports_unicode() if unicode is None else unicode
    label_width = max(display_width(row[0]) for row in rows)
    value_width = max(display_width(row[1]) for row in rows)
    bodies: list[str] = []
    for label, value, note in rows:
        line = f"{_pad(label, label_width)}  {_pad(value, value_width)}"
        if note:
            line += f"  {note}"
        bodies.append(line)
    content_width = max(display_width(line) for line in bodies)
    inner_width = display_width(indent) + content_width + 2
    if wide:
        top_left, top_right = "\u250c", "\u2510"
        bottom_left, bottom_right = "\u2514", "\u2518"
        horizontal, vertical = "\u2500", "\u2502"
    else:
        top_left = top_right = bottom_left = bottom_right = "+"
        horizontal, vertical = "-", "|"
    prefix = f"{horizontal} {title} "
    fill = max(1, inner_width - display_width(prefix))
    lines = [f"{top_left}{prefix}{horizontal * fill}{top_right}"]
    for body in bodies:
        padding = " " * max(0, content_width - display_width(body))
        lines.append(f"{vertical} {indent}{body}{padding} {vertical}")
    lines.append(f"{bottom_left}{horizontal * inner_width}{bottom_right}")
    return lines


class StageReporter:
    """Render a stage rail plus one ticking detail line while a command runs."""

    def __init__(
        self,
        stages: Sequence[str],
        *,
        title: str = "algocode",
        stream: TextIO | None = None,
        enabled: bool = True,
        color: bool | None = None,
        unicode: bool | None = None,
        ambiguous_wide: bool | None = None,
    ) -> None:
        self._stages = tuple(stages)
        self._title = title
        self._stream = stream if stream is not None else sys.stderr
        self._enabled = bool(enabled) and bool(self._stages)
        self._interactive = self._enabled and _is_tty(self._stream)
        self._color = self._interactive if color is None else bool(color) and self._interactive
        self._ambiguous_wide = _infer_ambiguous_wide() if ambiguous_wide is None else ambiguous_wide
        if unicode is True:
            self._glyphs = _UNICODE_GLYPHS
        elif unicode is False:
            self._glyphs = _ASCII_GLYPHS
        else:
            self._glyphs = _UNICODE_GLYPHS if _supports_unicode(self._stream) else _ASCII_GLYPHS
        self._status = [_PENDING] * len(self._stages)
        self._durations: list[float | None] = [None] * len(self._stages)
        self._index = -1
        self._detail = ""
        self._stage_started_at: float | None = None
        self._completion_lines: list[str] = []
        self._drawn = 0
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def interactive(self) -> bool:
        return self._interactive

    def begin(self, label: str, detail: str = "") -> None:
        """Mark ``label`` active and start its elapsed clock."""
        self._guard(self._begin, label, detail)

    def update(self, detail: str) -> None:
        """Replace the active stage's detail line."""
        self._guard(self._update, detail)

    def complete(self, label: str, detail: str = "") -> None:
        """Mark ``label`` done and freeze its duration."""
        self._guard(self._complete, label, detail)

    def fail(self, reason: str, *, hint: str = "", label: str | None = None) -> None:
        """Mark the active (or named) stage failed and explain why."""
        self._guard(self._fail, reason, hint, label)

    def note(self, text: str) -> None:
        """Print a standing note without disturbing the rail."""
        self._guard(self._note, text)

    def close(self) -> None:
        """Stop the ticker and clear the live block."""
        self._guard(self._close)

    # -- internals ------------------------------------------------------

    def _guard(self, function, *args) -> None:
        if not self._enabled:
            return
        try:
            function(*args)
        except Exception:  # noqa: BLE001 - progress must never break the command
            pass

    def _index_of(self, label: str) -> int:
        try:
            return self._stages.index(label)
        except ValueError:
            return -1

    def _paint(self, text: str, code: str) -> str:
        if not self._color:
            return text
        return f"{code}{text}{_RESET}"

    def _width(self, text: str) -> int:
        return display_width(text, ambiguous_wide=self._ambiguous_wide)

    def _elapsed_stage(self) -> float:
        if self._stage_started_at is None:
            return 0.0
        return max(0.0, time.perf_counter() - self._stage_started_at)

    def _plain(self, text: str) -> None:
        self._stream.write(f"{self._title}: {text}\n")
        self._flush()

    def _flush(self) -> None:
        try:
            self._stream.flush()
        except (AttributeError, ValueError):
            pass

    def _begin(self, label: str, detail: str) -> None:
        index = self._index_of(label)
        if index < 0:
            return
        with self._lock:
            self._status[index] = _ACTIVE
            self._index = index
            self._detail = detail
            self._stage_started_at = time.perf_counter()
            self._ensure_ticker()
            if self._interactive:
                self._render_locked()
            elif detail:
                self._plain(f"{label}: {detail}")

    def _update(self, detail: str) -> None:
        with self._lock:
            self._detail = detail
            if self._index < 0:
                return
            if self._interactive:
                self._render_locked()
            else:
                self._plain(f"{self._stages[self._index]}: {detail}")

    def _complete(self, label: str, detail: str) -> None:
        index = self._index_of(label)
        if index < 0:
            return
        with self._lock:
            self._status[index] = _DONE
            self._durations[index] = self._elapsed_stage()
            if self._index == index:
                self._index = -1
                self._detail = ""
            if self._interactive:
                suffix = f" · {detail}" if detail else ""
                elapsed = format_duration(self._durations[index] or 0.0)
                self._completion_lines.append(
                    f"{self._title}:  {label} {self._glyphs['done'].strip()} ({elapsed}){suffix}"
                )
                self._render_locked()
                self._flush()
            else:
                suffix = f" · {detail}" if detail else ""
                elapsed = format_duration(self._durations[index] or 0.0)
                self._plain(f"{label} {self._glyphs['done'].strip()} ({elapsed}){suffix}")

    def _fail(self, reason: str, hint: str, label: str | None) -> None:
        with self._lock:
            index = self._index_of(label) if label else self._index
            if index < 0:
                if reason:
                    self._plain(f"failed: {reason}")
                return
            self._status[index] = _FAILED
            self._durations[index] = self._elapsed_stage()
            self._index = -1
            if self._interactive:
                self._completion_lines.append(
                    f"{self._title}: {self._stages[index]} "
                    f"{self._glyphs['failed'].strip()}: {reason}"
                )
                if hint:
                    self._completion_lines.append(f"{self._title}   {hint}")
                self._render_locked()
                self._flush()
            else:
                extra = f" ({hint})" if hint else ""
                self._plain(f"{self._stages[index]} failed: {reason}{extra}")

    def _note(self, text: str) -> None:
        with self._lock:
            if self._interactive:
                self._completion_lines.append(f"{self._title} {self._glyphs['note']} {text}")
                self._render_locked()
            else:
                self._plain(f"{self._glyphs['note']} {text}")

    def _close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        with self._lock:
            self._erase_locked()
            if self._completion_lines:
                self._stream.write("\n".join(self._completion_lines) + "\n")
            else:
                self._stream.write("\n")
            self._flush()

    def _ensure_ticker(self) -> None:
        if not self._interactive or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._tick, name="algocode-progress", daemon=True)
        self._thread.start()

    def _tick(self) -> None:
        while not self._stop.wait(0.5):
            try:
                with self._lock:
                    if self._index >= 0 and self._status[self._index] == _ACTIVE:
                        self._render_locked()
            except Exception:  # noqa: BLE001
                continue

    def _rail(self) -> tuple[str, str, int]:
        """Return (plain rail, styled rail, cell offset of the active node).

        Offsets are terminal cells, not characters: CJK stage labels and the
        box-drawing separators occupy more cells than ``len`` reports.
        """
        sep_plain = self._glyphs["arrow"]
        sep_styled = self._paint(sep_plain, _DIM)
        plain_nodes: list[str] = []
        styled_nodes: list[str] = []
        offsets: list[int] = []
        cursor = self._width(self._title) + 2
        for index, label in enumerate(self._stages):
            status = self._status[index]
            if status == _DONE:
                continue
            if status == _ACTIVE:
                plain = f"[{label}]"
                styled = self._paint(plain, f"{_CYAN}{_BOLD}")
            elif status == _FAILED:
                plain = f"{label}{self._glyphs['failed']}"
                styled = self._paint(plain, _RED)
            else:
                plain = label
                styled = self._paint(label, _DIM)
            offsets.append(cursor)
            plain_nodes.append(plain)
            styled_nodes.append(styled)
            cursor += self._width(plain) + self._width(sep_plain)
        plain_rail = f"{self._title}  " + sep_plain.join(plain_nodes)
        styled_rail = self._paint(self._title, _BOLD) + "  " + sep_styled.join(styled_nodes)
        active_offset = self._width(self._title) + 2 if self._index >= 0 else 0
        return plain_rail, styled_rail, active_offset

    def _build_lines(self) -> list[str]:
        visible = [index for index, status in enumerate(self._status) if status != _DONE]
        if not visible:
            return list(self._completion_lines)
        _plain_rail, styled_rail, active_offset = self._rail()
        lines = [styled_rail]
        if self._index >= 0:
            detail = self._detail or "in progress"
            elapsed = format_duration(self._elapsed_stage())
            marker = self._glyphs["active"]
            indent = " " * max(0, active_offset)
            lines.append(f"{indent}{self._paint(marker, _CYAN)} {detail} · {elapsed}")
        lines.extend(self._completion_lines)
        return lines

    def _render_locked(self) -> None:
        if not self._interactive:
            return
        self._write_block_locked(self._build_lines())

    def _refresh_detail_locked(self) -> None:
        self._render_locked()

    def _write_block_locked(self, lines: Sequence[str]) -> None:
        self._erase_locked()
        self._stream.write("\n".join(lines) + "\n")
        self._flush()
        self._drawn = len(lines)

    def _erase_locked(self) -> None:
        if not self._interactive or self._drawn <= 0:
            return
        self._stream.write(f"\x1b[{self._drawn}A\r\x1b[0J")
        self._drawn = 0

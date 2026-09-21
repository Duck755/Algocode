"""Decode subprocess output without relying on the Windows locale."""

from __future__ import annotations

import codecs
import locale
import subprocess
from collections.abc import Sequence
from typing import Any


def decode_process_output(data: bytes | None) -> str:
    """Decode process output using BOM, UTF-8, locale, and safe fallbacks."""

    if not data:
        return ""
    if data.startswith(codecs.BOM_UTF8):
        return _without_bom(data.decode("utf-8-sig", errors="replace"))
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return _without_bom(data.decode("utf-16", errors="replace"))
    utf16_encoding = _utf16_encoding_without_bom(data)
    if utf16_encoding is not None:
        return _without_bom(data.decode(utf16_encoding, errors="replace"))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return data.decode(locale.getpreferredencoding(False))
    except (LookupError, UnicodeDecodeError):
        return data.decode("utf-8", errors="replace")


def run_text(
    command: Sequence[str],
    **kwargs: Any,
) -> subprocess.CompletedProcess[str]:
    """Run a command with bytes output and decode it portably."""

    options = dict(kwargs)
    options.pop("text", None)
    options.pop("encoding", None)
    options.pop("errors", None)
    options.pop("universal_newlines", None)
    if not any(key in options for key in ("capture_output", "stdout", "stderr")):
        options["capture_output"] = True
    completed = subprocess.run(command, **options)
    return subprocess.CompletedProcess(
        completed.args,
        completed.returncode,
        decode_process_output(completed.stdout),
        decode_process_output(completed.stderr),
    )


def _utf16_encoding_without_bom(data: bytes) -> str | None:
    if len(data) < 4:
        return None
    even_zeros = data[0::2].count(0)
    odd_zeros = data[1::2].count(0)
    threshold = max(2, len(data) // 8)
    if odd_zeros >= threshold and odd_zeros > even_zeros * 2:
        return "utf-16-le"
    if even_zeros >= threshold and even_zeros > odd_zeros * 2:
        return "utf-16-be"
    return None


def _without_bom(text: str) -> str:
    return text.removeprefix("\ufeff")

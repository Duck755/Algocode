"""Conservative context token estimation."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    by_chars = (len(text) + 2) // 3
    by_bytes = (len(text.encode("utf-8")) + 3) // 4
    return max(1, by_chars, by_bytes)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    char_budget = max_tokens * 3
    if len(text) <= char_budget:
        return text
    marker = "\n[context truncated]"
    marker_tokens = estimate_tokens(marker)
    if max_tokens <= marker_tokens:
        return marker[: max_tokens * 3]
    body_budget = max(0, (max_tokens - marker_tokens) * 3)
    return text[:body_budget] + marker

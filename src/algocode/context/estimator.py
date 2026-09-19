"""Tokenizer-aware context sizing with a conservative fallback."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _tokenizer():
    try:
        import tiktoken

        return tiktoken.get_encoding("cl100k_base")
    except Exception:
        return None


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    encoder = _tokenizer()
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception:
            pass
    by_chars = (len(text) + 2) // 3
    by_bytes = (len(text.encode("utf-8")) + 3) // 4
    return max(1, by_chars, by_bytes)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    if max_tokens <= 0:
        return ""
    encoder = _tokenizer()
    if encoder is not None:
        try:
            tokens = encoder.encode(text, disallowed_special=())
            if len(tokens) <= max_tokens:
                return text
            marker = "\n[context truncated]"
            marker_tokens = len(encoder.encode(marker, disallowed_special=()))
            if max_tokens <= marker_tokens:
                return ""
            return encoder.decode(tokens[: max_tokens - marker_tokens]) + marker
        except Exception:
            pass
    char_budget = max_tokens * 3
    if len(text) <= char_budget:
        return text
    marker = "\n[context truncated]"
    marker_tokens = estimate_tokens(marker)
    if max_tokens <= marker_tokens:
        return marker[: max_tokens * 3]
    body_budget = max(0, (max_tokens - marker_tokens) * 3)
    return text[:body_budget] + marker

"""Deterministic seed derivation for reproducible optimization runs."""

from __future__ import annotations

import hashlib


def derive_seed(run_seed: int, *components: object) -> int:
    """Derive a stable component seed from a global run seed."""

    payload = "\0".join(str(component) for component in components).encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    component_hash = int.from_bytes(digest[:4], "big")
    return (run_seed ^ component_hash) & 0x7FFFFFFF


def component_seeds(
    run_seed: int,
    components: tuple[tuple[object, ...], ...],
) -> tuple[int, ...]:
    """Derive one seed per component tuple."""

    return tuple(derive_seed(run_seed, *component) for component in components)

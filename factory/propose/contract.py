"""Frozen twin contracts and deterministic contract validation. Owner: Akshat."""
from __future__ import annotations

from factory.schema import Contract, Seed


def validate_contracts(a: Contract, b: Contract) -> list[str]:
    """Return validation error messages for twin contracts A and B (empty means valid)."""
    raise NotImplementedError


def write_contracts(seed: Seed, surface: str) -> tuple[Contract, Contract]:
    """Generate and validate frozen twin contracts A and B from a seed."""
    raise NotImplementedError

"""Gate G8: novelty check against click main, docs, CHANGES, and issues/PRs. Owner: Akshat."""
from __future__ import annotations

from factory.schema import GateResult, Seed


def novelty_gate(seed: Seed) -> GateResult:
    """Return GateResult(gate='G8', ...) checking that seed is not already in click."""
    raise NotImplementedError

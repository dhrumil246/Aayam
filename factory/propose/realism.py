"""Gate G9: realism rubric check for a proposed seed. Owner: Akshat."""
from __future__ import annotations

from factory.schema import GateResult, Seed


def realism_gate(seed: Seed, surface: str) -> GateResult:
    """Return GateResult(gate='G9', ...) scoring click-design fit, reason, and usefulness."""
    raise NotImplementedError

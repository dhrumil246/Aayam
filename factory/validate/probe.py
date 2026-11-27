"""G5: pivot probe replay and cross-grading of the twins.

Owner: Urja.
"""
from __future__ import annotations

from factory.schema import GateResult, Pair


def g5_twin_separation(pair: Pair) -> GateResult:
    """Replay the probe through both references and cross-grade them (gate="G5")."""
    raise NotImplementedError

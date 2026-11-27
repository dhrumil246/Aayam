"""G7: requirement <-> test <-> mutant traceability.

Owner: Urja.
"""
from __future__ import annotations

from factory.schema import GateResult, Pair


def g7_trace(pair: Pair, side: str, g6: GateResult) -> GateResult:
    """Check every requirement has a test and a killed mutant (gate="G7")."""
    raise NotImplementedError

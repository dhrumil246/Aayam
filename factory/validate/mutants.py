"""G6: requirement-targeted mutants and the kill check.

Owner: Urja.
"""
from __future__ import annotations

from pathlib import Path

from factory.schema import Contract, GateResult, Pair, Patch


def make_mutants(contract: Contract, ticket: str, reference: Patch, out_dir: Path) -> list[Patch]:
    """Write one plausible wrong patch per requirement into `out_dir`."""
    raise NotImplementedError


def g6_mutants(pair: Pair, side: str, mutants: list[Patch]) -> GateResult:
    """Run the grader on each mutant (gate="G6", detail["killed"], detail["survivors"])."""
    raise NotImplementedError

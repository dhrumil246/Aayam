"""Differential search between two patched copies of click.

Owner: Urja. A lead finder, not an oracle: findings become tests only after
expectations are derived from the tickets. Hypothesis shrinking gives a
small example, not a guaranteed shortest one. Also used by Heet (solver vs
reference), so `patch_b` can be any patch.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from factory.schema import Finding, FindingLabel, Invocation, RepoPin

if TYPE_CHECKING:
    from hypothesis.strategies import SearchStrategy


def invocations(grammar: dict) -> SearchStrategy[Invocation]:
    """Hypothesis strategy drawing invocations from a contract grammar (format in AGENTS.md)."""
    raise NotImplementedError


def diff_search(pin: RepoPin, patch_a: str | None, patch_b: str | None, demo_app: str,
                grammar: dict, budget: int = 200) -> list[Finding]:
    """Find, shrink and fresh-replay inputs where the two patches disagree."""
    raise NotImplementedError


def classify_finding(finding: Finding, ticket_a: str, ticket_b: str) -> FindingLabel:
    """Label a finding as "pivot", "shared" or "open" against the two tickets."""
    raise NotImplementedError

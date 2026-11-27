"""Ticket-derived expectations for a probe.

Owner: Urja. Expected outcomes come from one ticket only, never from a
reference's output. Imported by Heet's code, so keep it free of any
reference-patch knowledge.
"""
from __future__ import annotations

from factory.schema import Assertion, Invocation, Outcome


def derive_expectations(ticket: str, probe: Invocation, requirement_id: str) -> list[Assertion]:
    """Ask a model, shown only `ticket` and `probe`, what the ticket determines about the outcome."""
    raise NotImplementedError


def validate_assertion(a: Assertion) -> list[str]:
    """Return problems with `a.python` (empty list = safe to evaluate)."""
    raise NotImplementedError


def check(assertions: list[Assertion], outcome: Outcome) -> list[tuple[Assertion, bool]]:
    """Evaluate each validated assertion against `outcome`."""
    raise NotImplementedError

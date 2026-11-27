"""Hidden grader generation, naming checks and repair.

Owner: Urja. Graders are written from the contract and ticket only, never
from a reference patch. Tests are named `test_new__R<n>__...` or
`test_preserved__R<n>__...` (see AGENTS.md).
"""
from __future__ import annotations

from pathlib import Path

from factory.schema import Assertion, Contract, Finding, Invocation


def write_grader(contract: Contract, ticket: str, assertions: list[Assertion], out: Path) -> str:
    """Write a self-contained grader file to `out` and return its path."""
    raise NotImplementedError


def check_grader_names(path: str, contract: Contract) -> list[str]:
    """Return naming/coverage problems in the grader at `path` (empty list = ok)."""
    raise NotImplementedError


def repair_grader(contract: Contract, ticket: str, grader_path: str, failure: str,
                  findings: list[Finding]) -> str:
    """Rewrite the grader using the failing gate's text and pivot findings; return its path."""
    raise NotImplementedError


def probe_test_source(assertions: list[Assertion], probe: Invocation, requirement_id: str) -> str:
    """Return pytest source for one `test_new__<req>__pivot_probe` test."""
    raise NotImplementedError

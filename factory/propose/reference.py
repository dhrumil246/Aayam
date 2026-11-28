"""Reference patch generation and repair against the pinned click repo. Owner: Akshat."""
from __future__ import annotations

from pathlib import Path

from factory.schema import Contract, Patch, RepoPin


def write_reference(contract: Contract, ticket: str, pin: RepoPin, out: Path) -> Patch:
    """Write a reference unified diff for one side, verified in the sandbox."""
    raise NotImplementedError


def repair_reference(contract: Contract, ticket: str, pin: RepoPin, patch: Patch, failure: str) -> Patch:
    """Repair a reference patch given a sandbox or shared-clause failure."""
    raise NotImplementedError

"""Public Markdown ticket rendering from a frozen contract. Owner: Akshat."""
from __future__ import annotations

from factory.schema import Contract, Seed


def render_ticket(contract: Contract, seed: Seed) -> str:
    """Render a standalone Markdown ticket for one side without leaking the twin."""
    raise NotImplementedError

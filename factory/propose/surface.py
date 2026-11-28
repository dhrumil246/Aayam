"""Click public API and extension-point surface map. Owner: Akshat."""
from __future__ import annotations

from factory.schema import RepoPin


def discover_surface(pin: RepoPin) -> str:
    """Return a concise summary of click's public API and extension points."""
    raise NotImplementedError

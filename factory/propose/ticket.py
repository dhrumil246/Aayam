"""Public Markdown ticket rendering from a frozen contract. Owner: Akshat."""
from __future__ import annotations

from factory.schema import Contract, Seed


def _title_from_feature(feature: str) -> str:
    first = feature.strip().splitlines()[0].split(".")[0].strip()
    return first[:80] if len(first) > 80 else first


def render_ticket(contract: Contract, seed: Seed) -> str:
    """Render a standalone Markdown ticket for one side without leaking the twin."""
    reason = seed.reason_a if contract.side == "A" else seed.reason_b
    title = _title_from_feature(seed.feature)

    req_lines = "\n".join(f"{i}. **{r.id}:** {r.text}" for i, r in enumerate(contract.requirements, 1))
    if contract.open_items:
        open_lines = "\n".join(f"- {item}" for item in contract.open_items)
    else:
        open_lines = "- Nothing is left open; follow the requirements above."

    return (
        f"# {title}\n\n"
        f"## Background\n\n"
        f"{seed.feature.strip()}\n\n"
        f"{reason.strip()}\n\n"
        f"## Requirements\n\n"
        f"{req_lines}\n\n"
        f"## Public API\n\n"
        f"```python\n{contract.public_api.strip()}\n```\n\n"
        f"## Left to you\n\n"
        f"{open_lines}\n\n"
        f"## How it will be checked\n\n"
        f"- Existing `click` tests must continue to pass.\n"
        f"- New tests will invoke a `click` command using `CliRunner` and the public `click` API.\n"
    )

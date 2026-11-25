"""Basic validation gates G0-G4. Owner: Dhrumil."""
from __future__ import annotations

from factory import adapter_click, sandbox
from factory.schema import GateResult, RepoPin


def _failed_ids(rows: list[dict]) -> set[str]:
    return {r["nodeid"] for r in rows if r["outcome"] == "failed"}


def g0_baseline(pin: RepoPin, runs: int = 3) -> GateResult:
    """Existing suite on the unpatched pin, run `runs` times. Tests that flip are recorded as FLAKY."""
    results = [_failed_ids(sandbox._run_pytest(pin, None, [adapter_click.EXISTING_TESTS])[0]) for _ in range(runs)]
    always = set.intersection(*results)
    flaky = set.union(*results) - always
    adapter_click.save_flaky(sorted(set(adapter_click.FLAKY) | flaky))
    failed = sorted(t for t in always if not adapter_click.is_excluded(t))
    return GateResult("G0", passed=not failed, detail={"failed": failed, "flaky": sorted(flaky), "runs": runs})

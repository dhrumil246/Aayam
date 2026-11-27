"""G5: pivot probe replay and cross-grading of the twins.

Owner: Urja. Expected outcomes are the ticket-derived assertions in
`pair.expectations`; the references' outputs are only checked against them,
never used as expectations.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from factory import sandbox, worker
from factory.gates_basic import parse_test_name
from factory.schema import GateResult, Pair
from factory.validate.expect import check
from factory.validate.search import same_outcome

TWIN = {"A": "B", "B": "A"}


def g5_twin_separation(pair: Pair) -> GateResult:
    """Replay the probe through both references and cross-grade them (gate="G5").

    Passes only if: both graders contain the pivot probe test; the two
    references give different probe outcomes; each satisfies its own
    ticket's pivot assertions and fails its twin's; and each reference fails
    its twin's grader on a pivot `test_new__` test with an assertion failure.
    """
    detail: dict = {"outcomes": {}, "own": {}, "twin": {}, "cross": {}}

    def fail(reason: str) -> GateResult:
        detail["reason"] = reason
        return GateResult("G5", passed=False, detail=detail)

    pivots = {s: pair.contracts[s].pivot().id for s in TWIN}
    for s in TWIN:
        name = f"test_new__{pivots[s]}__pivot_probe"
        if not re.search(rf"^def {name}\(", Path(pair.graders[s]).read_text(), re.M):
            return fail(f"grader {s} has no {name} test")
    probe = pair.contracts["A"].probe
    if pair.contracts["B"].probe != probe:
        return fail("contracts A and B have different probes")
    asserts = {s: [a for a in pair.expectations.get(s, []) if a.requirement_id == pivots[s]] for s in TWIN}
    for s in TWIN:
        if not asserts[s]:
            return fail(f"no ticket-derived pivot assertions for {s}")

    out = {s: worker.fresh_call(pair.pin, pair.references[s].path, pair.contracts[s].demo_app, probe)
           for s in TWIN}
    detail["outcomes"] = {s: dataclasses.asdict(o) for s, o in out.items()}
    if same_outcome(out["A"], out["B"]):
        return fail("probe does not separate twins")
    for s in TWIN:
        detail["own"][s] = all(ok for _, ok in check(asserts[s], out[s]))
        detail["twin"][s] = all(ok for _, ok in check(asserts[TWIN[s]], out[s]))
    for s in TWIN:
        if not detail["own"][s]:
            return fail(f"ref {s} does not meet its own ticket's pivot assertions")
        if detail["twin"][s]:
            return fail(f"ref {s} also meets ticket {TWIN[s]}'s pivot assertions, so the probe doesn't tell the twins apart")

    for s in TWIN:
        t = TWIN[s]
        run = sandbox.run_tests(pair.pin, [pair.references[s].path], [pair.graders[t]], pair_id=pair.seed.pair_id)
        pivot_failures = {tid: kind for tid, kind in run.failed.items()
                          if parse_test_name(tid)[0] == "new" and pivots[t] in parse_test_name(tid)[1]}
        detail["cross"][s] = {"grader": t, "pivot_failures": pivot_failures, "log": run.log_path}
        if not pivot_failures:
            return fail(f"ref {s} passes grader {t} on {pivots[t]}")
        if "assertion" not in pivot_failures.values():
            kinds = sorted(set(pivot_failures.values()))
            return fail(f"ref {s} fails grader {t} on {pivots[t]} only with {kinds}, not an assertion failure")
    return GateResult("G5", passed=True, detail=detail)

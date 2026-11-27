"""G7: requirement <-> test <-> mutant traceability.

Owner: Urja. Tests are read from the grader's test names; kills come from
G6's detail (`killed` and `mutant_requirements`).
"""
from __future__ import annotations

import ast
from pathlib import Path

from factory.gates_basic import parse_test_name
from factory.schema import GateResult, Pair
from factory.validate.grader import _test_functions


def g7_trace(pair: Pair, side: str, g6: GateResult) -> GateResult:
    """Check every requirement has a test and a killed mutant (gate="G7").

    Also fails if a test cites no requirement or an unknown one.
    """
    contract = pair.contracts[side]
    reqs = {r.id: {"tests": [], "killed_mutants": []} for r in contract.requirements}
    uncited, unknown = [], []
    for name in _test_functions(ast.parse(Path(pair.graders[side]).read_text())):
        kind, ids = parse_test_name(f"grader.py::{name}")
        if kind == "other":
            uncited.append(name)
        for r in ids:
            if r in reqs:
                reqs[r]["tests"].append(name)
            else:
                unknown.append(f"{name}: {r}")
    owners = g6.detail.get("mutant_requirements", {})
    for path in g6.detail.get("killed", {}):
        if owners.get(path) in reqs:
            reqs[owners[path]]["killed_mutants"].append(path)
    for entry in reqs.values():
        entry["tests"].sort()
        entry["killed_mutants"].sort()
    detail = {
        "requirements": reqs,
        "missing_tests": sorted(r for r, e in reqs.items() if not e["tests"]),
        "missing_kills": sorted(r for r, e in reqs.items() if not e["killed_mutants"]),
        "uncited_tests": sorted(uncited),
        "unknown_requirements": sorted(unknown),
    }
    passed = not (detail["missing_tests"] or detail["missing_kills"] or uncited or unknown)
    return GateResult("G7", passed=passed, detail=detail)

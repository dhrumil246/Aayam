"""Basic validation gates G0-G4. Owner: Dhrumil."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from factory import adapter_click, sandbox
from factory.schema import GateResult, Pair, RepoPin


def _failed_ids(rows: list[dict]) -> set[str]:
    return {r["nodeid"] for r in rows if r["outcome"] == "failed"}


def g0_baseline(pin: RepoPin, runs: int = 3) -> GateResult:
    """Existing suite on the unpatched pin, run `runs` times. Tests that flip are recorded as FLAKY."""
    results = []
    for _ in range(runs):
        rows, _log, code = sandbox._run_pytest(pin, None, [adapter_click.EXISTING_TESTS])
        if code not in (0, 1):
            return GateResult("G0", passed=False, detail={"failed": ["<pytest did not complete>"],
                                                          "exit_code": code, "flaky": [], "runs": runs})
        results.append(_failed_ids(rows))
    always = set.intersection(*results)
    flaky = set.union(*results) - always
    adapter_click.save_flaky(sorted(set(adapter_click.FLAKY) | flaky))
    failed = sorted(t for t in always if not adapter_click.is_excluded(t))
    return GateResult("G0", passed=not failed, detail={"failed": failed, "flaky": sorted(flaky), "runs": runs})


_NAME = re.compile(r"^test_(new|preserved)__((?:R\d+_?)+)__")


def parse_test_name(node_id: str) -> tuple[str, list[str]]:
    """`x.py::test_new__R2_R4__foo[p]` -> ("new", ["R2", "R4"]); anything else -> ("other", [])."""
    name = node_id.split("::")[-1].split("[")[0]
    m = _NAME.match(name)
    if not m:
        return "other", []
    return m.group(1), [r for r in m.group(2).split("_") if r]


def _grader_run(pair: Pair, side: str, patched: bool, repeat: int = 1):
    patches = [pair.references[side].path] if patched else []
    return sandbox.run_tests(pair.pin, patches, [pair.graders[side]], repeat=repeat, pair_id=pair.seed.pair_id)


def g1_fail_before(pair: Pair, side: str) -> GateResult:
    """On base: every test_new__ fails for an expected reason; every test_preserved__ passes."""
    run = _grader_run(pair, side, patched=False)
    ids = set(run.passed) | set(run.failed)
    kind = {t: parse_test_name(t)[0] for t in ids}
    detail = {
        "bad_failures": {t: k for t, k in run.failed.items() if k not in ("assertion", "missing_api")},
        "new_passing_on_base": sorted(t for t in run.passed if kind[t] == "new"),
        "preserved_failing_on_base": sorted(t for t in run.failed if kind[t] == "preserved"),
        "unnamed": sorted(t for t in ids if kind[t] == "other" and "::" in t),
        "new_failed": sorted(t for t in run.failed if kind[t] == "new"),
        "log": run.log_path,
    }
    ok = (not detail["bad_failures"] and not detail["new_passing_on_base"] and not detail["unnamed"]
          and not detail["preserved_failing_on_base"] and detail["new_failed"])
    return GateResult("G1", passed=bool(ok), detail=detail)


def g2_pass_after(pair: Pair, side: str) -> GateResult:
    """On the reference: the grader and click's existing suite all pass."""
    grader = _grader_run(pair, side, patched=True)
    suite = sandbox.run_tests(pair.pin, [pair.references[side].path], pair_id=pair.seed.pair_id)
    detail = {"grader_failed": grader.failed, "suite_failed": sorted(suite.failed),
              "grader_log": grader.log_path, "suite_log": suite.log_path}
    return GateResult("G2", passed=not grader.failed and not suite.failed and bool(grader.passed), detail=detail)


def g3_stability(pair: Pair, side: str, n: int = 5) -> GateResult:
    """The grader gives identical results on base and on the reference, n times over."""
    seen: dict[str, set] = {"base": set(), "ref": set()}
    for _ in range(n):
        for key, patched in (("base", False), ("ref", True)):
            run = _grader_run(pair, side, patched)
            seen[key].add((tuple(sorted(run.passed)), tuple(sorted(run.failed.items()))))
    unstable = [k for k, v in seen.items() if len(v) > 1]
    return GateResult("G3", passed=not unstable, detail={"unstable": unstable, "runs": n})


def _private(parts: list[str]) -> bool:
    return any(p.startswith("_") and not (p.startswith("__") and p.endswith("__")) for p in parts)


def g4_public_api(grader_path: str) -> GateResult:
    """AST scan: the grader touches only click's public API."""
    tree = ast.parse(Path(grader_path).read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "click":
            if _private(node.module.split(".")) or _private([a.name for a in node.names]):
                hits.append(f"line {node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Import):
            hits += [f"line {node.lineno}: import {a.name}" for a in node.names
                     if a.name.split(".")[0] == "click" and _private(a.name.split("."))]
        elif isinstance(node, ast.Attribute):
            chain, cur = [node.attr], node.value
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id == "click" and _private(chain):
                hits.append(f"line {node.lineno}: click.{'.'.join(reversed(chain))}")
    return GateResult("G4", passed=not hits, detail={"private_uses": sorted(set(hits))})

"""One twin pair end to end: propose, contract, write, validate, repair, accept or reject. Owner: Dhrumil.

Stage functions belong to their owners (AGENTS.md) and are looked up by name
when a stage runs, so this file never edits or re-implements them. Every stage
is saved under runs/<pair_id>/ (pair.json + state.json), so a killed run
resumes where it stopped and a finished pair is never regenerated.
"""
from __future__ import annotations

import dataclasses
import importlib
import json
import shutil
from pathlib import Path

from factory import adapter_click
from factory.schema import GateResult, Pair, Patch, RepoPin, _build, load, save

STAGES = {
    "surface": "factory.propose.surface:discover_surface",
    "seed": "factory.propose.seeds:propose_seed",
    "novelty": "factory.propose.novelty:novelty_gate",
    "realism": "factory.propose.realism:realism_gate",
    "contracts": "factory.propose.contract:write_contracts",
    "ticket": "factory.propose.ticket:render_ticket",
    "reference": "factory.propose.reference:write_reference",
    "repair_reference": "factory.propose.reference:repair_reference",
    "expect": "factory.validate.expect:derive_expectations",
    "grader": "factory.validate.grader:write_grader",
    "repair_grader": "factory.validate.grader:repair_grader",
    "g5": "factory.validate.probe:g5_twin_separation",
    "mutants": "factory.validate.mutants:make_mutants",
    "g6": "factory.validate.mutants:g6_mutants",
    "g7": "factory.validate.trace:g7_trace",
    "heldout": "factory.evaluate.heldout:make_heldout",
    "valid_alt": "factory.evaluate.heldout:valid_alternative",
    "g6h": "factory.evaluate.heldout:g6h_heldout",
    "blind_solve": "factory.evaluate.solver:blind_solve",
    "diagnose": "factory.evaluate.diagnose:diagnose",
    "g1": "factory.gates_basic:g1_fail_before",
    "g2": "factory.gates_basic:g2_pass_after",
    "g3": "factory.gates_basic:g3_stability",
    "g4": "factory.gates_basic:g4_public_api",
}
SIDES = ("A", "B")
MAX_REPAIRS = 2


def _fn(stage: str):
    module, name = STAGES[stage].split(":")
    return getattr(importlib.import_module(module), name)


def run_dir(pair_id: str) -> Path:
    return adapter_click._runs() / pair_id


def load_state(pair_id: str) -> dict:
    path = run_dir(pair_id) / "state.json"
    return json.loads(path.read_text()) if path.exists() else {"done": []}


def _save(pair: Pair, state: dict) -> None:
    save(pair, run_dir(pair.seed.pair_id) / "pair.json")
    (run_dir(pair.seed.pair_id) / "state.json").write_text(json.dumps(state, indent=2, sort_keys=True))


def _patches(raw) -> list[Patch]:
    return _build(list[Patch], raw)


def _existing_features() -> list[str]:
    root = adapter_click._runs()
    return [load(Pair, p).seed.feature for p in sorted(root.glob("*/pair.json"))] if root.exists() else []


def _finish(pair: Pair, state: dict, status: str, reason: str | None = None) -> Pair:
    pair.status, pair.reject_reason = status, reason
    state["done"].append("finished")
    _save(pair, state)
    return pair


def _reject(pair: Pair, state: dict, gate: GateResult) -> Pair:
    detail = gate.detail.get("reason") or json.dumps(gate.detail, sort_keys=True, default=str)[:300]
    return _finish(pair, state, "rejected", f"{gate.gate}: {detail}")


def _record(pair: Pair, result: GateResult, side: str | None) -> None:
    result.detail.setdefault("side", side)
    pair.gates = [g for g in pair.gates if not (g.gate == result.gate and g.detail.get("side") == side)]
    pair.gates.append(result)


def _validate(pair: Pair, state: dict) -> tuple[GateResult, str | None] | None:
    """Run G1-G7 once; return the first failure and its side (None for pair-level gates)."""
    for side in SIDES:
        for gate in ("g1", "g2", "g3"):
            result = _fn(gate)(pair, side)
            _record(pair, result, side)
            if not result.passed:
                return result, side
        result = _fn("g4")(pair.graders[side])
        _record(pair, result, side)
        if not result.passed:
            return result, side
    result = _fn("g5")(pair)
    _record(pair, result, None)
    if not result.passed:
        return result, None
    for side in SIDES:
        if side not in state.setdefault("mutants", {}):
            out = run_dir(pair.seed.pair_id) / "patches" / f"mutants_{side}"
            made = _fn("mutants")(pair.contracts[side], pair.tickets[side], pair.references[side], out)
            state["mutants"][side] = [dataclasses.asdict(m) for m in made]
        g6 = _fn("g6")(pair, side, _patches(state["mutants"][side]))
        _record(pair, g6, side)
        if not g6.passed:
            return g6, side
        g7 = _fn("g7")(pair, side, g6)
        _record(pair, g7, side)
        if not g7.passed:
            return g7, side
    return None


def _repair(pair: Pair, state: dict, failure: GateResult, side: str | None) -> None:
    """Existing-suite failures go to the reference author; everything else to the grader author."""
    text = json.dumps({"gate": failure.gate, "detail": failure.detail}, sort_keys=True, default=str)
    if failure.gate == "G2" and failure.detail.get("suite_failed") and side is not None:
        pair.references[side] = _fn("repair_reference")(pair.contracts[side], pair.tickets[side], pair.pin,
                                                         pair.references[side], text)
        state.get("mutants", {}).pop(side, None)  # mutants derive from the reference
        return
    for s in ([side] if side else SIDES):
        pair.graders[s] = _fn("repair_grader")(pair.contracts[s], pair.tickets[s], pair.graders[s], text,
                                               pair.findings)


def run_pair(family: str, pin: RepoPin, pair_id: str | None = None) -> Pair:
    """Generate and validate one twin pair; resumes runs/<pair_id>/ if it exists."""
    state = load_state(pair_id) if pair_id else {"done": []}
    done = state["done"]
    if "finished" in done:
        return load(Pair, run_dir(pair_id) / "pair.json")

    if "seed" in done:
        pair = load(Pair, run_dir(pair_id) / "pair.json")
    else:
        state["surface"] = _fn("surface")(pin)
        done.append("surface")
        seed = _fn("seed")(state["surface"], family, _existing_features())
        if pair_id:
            seed.pair_id = pair_id
        while (run_dir(seed.pair_id) / "state.json").exists():
            seed.pair_id += "-2"
        pair = Pair(seed=seed, pin=pin)
        done.append("seed")
        _save(pair, state)
    rd = run_dir(pair.seed.pair_id)

    for name, stage, args in (("G8", "novelty", (pair.seed,)), ("G9", "realism", (pair.seed, state["surface"]))):
        if name not in done:
            result = _fn(stage)(*args)
            _record(pair, result, None)
            done.append(name)
            _save(pair, state)
            if not result.passed:
                return _reject(pair, state, result)

    if "contracts" not in done:
        a, b = _fn("contracts")(pair.seed, state["surface"])
        pair.contracts = {"A": a, "B": b}
        done.append("contracts")
        _save(pair, state)

    if "tickets" not in done:
        pair.tickets = {s: _fn("ticket")(pair.contracts[s], pair.seed) for s in SIDES}
        done.append("tickets")
        _save(pair, state)

    # Held-out patches see only the ticket and are made before any reference exists.
    if "heldout" not in done:
        state["heldout"] = {s: [dataclasses.asdict(p) for p in
                                _fn("heldout")(pair.tickets[s], pin, rd / "patches" / f"heldout_{s}")] for s in SIDES}
        state["valid_alt"] = {s: dataclasses.asdict(
            _fn("valid_alt")(pair.tickets[s], pin, rd / "patches" / f"valid_alt_{s}.patch")) for s in SIDES}
        done.append("heldout")
        _save(pair, state)

    if "references" not in done:
        pair.references = {s: _fn("reference")(pair.contracts[s], pair.tickets[s], pin,
                                                rd / "patches" / f"ref_{s}.patch") for s in SIDES}
        done.append("references")
        _save(pair, state)

    if "expectations" not in done:
        pair.expectations = {s: _fn("expect")(pair.tickets[s], pair.contracts[s].probe,
                                              pair.contracts[s].pivot().id) for s in SIDES}
        done.append("expectations")
        _save(pair, state)

    if "graders" not in done:
        for s in SIDES:
            path = _fn("grader")(pair.contracts[s], pair.tickets[s], pair.expectations[s],
                                 rd / "graders" / f"test_{s}.py")
            pair.graders[s] = str(path)
            shutil.copy(path, rd / "graders" / f"test_{s}.initial.py")  # snapshot before any repair (G6h)
        done.append("graders")
        _save(pair, state)

    repairs = state.setdefault("repairs", [])
    while True:
        failed = _validate(pair, state)
        _save(pair, state)
        if failed is None:
            break
        result, side = failed
        if len(repairs) >= MAX_REPAIRS:
            return _reject(pair, state, result)
        repairs.append({"gate": result.gate, "side": side})
        _repair(pair, state, result, side)
        _save(pair, state)

    # G6h is measurement only: a failure rejects the pair and never feeds a repair.
    for s in SIDES:
        patches = _patches(state["heldout"][s]) + _patches([state["valid_alt"][s]])
        result = _fn("g6h")(pair, s, patches)
        _record(pair, result, s)
        if not result.passed:
            return _reject(pair, state, result)
    done.append("G6h")
    return _finish(pair, state, "accepted")


def evaluate_pair(pair_id: str, models: list[str]) -> Pair:
    """Blind-solve each ticket with each model and diagnose the result; skips work already saved."""
    pair = load(Pair, run_dir(pair_id) / "pair.json")
    state = load_state(pair_id)
    solver = state.setdefault("solver", {})
    for model in models:
        for s in SIDES:
            key = f"{model}:{s}"
            if key in solver:
                continue
            out = run_dir(pair_id) / "patches" / "solver" / f"{model}_{s}.patch"
            patch = _fn("blind_solve")(pair.tickets[s], pair.pin, model, out)
            solver[key] = {"patch": dataclasses.asdict(patch), "diagnosis": _fn("diagnose")(pair, s, patch)}
            _save(pair, state)
    return pair

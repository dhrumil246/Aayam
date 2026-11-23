"""Shared data types for the whole factory.

Owner: Dhrumil. Changes are ADDITIVE ONLY (new optional fields, new classes),
in a PR titled "[schema] ...", announced in team chat before merge.
Never rename or remove a field another person uses.

Every stage passes these objects; every run is stored as JSON via save()/load().
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import types
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Side = Literal["A", "B"]
FailKind = Literal["assertion", "missing_api", "collection", "error"]
PatchKind = Literal["reference", "mutant", "heldout_wrong", "valid_alt", "solver"]
FindingLabel = Literal["pivot", "shared", "open"]
PairStatus = Literal["draft", "accepted", "rejected"]


@dataclass
class RepoPin:
    repo: str  # "pallets/click"
    tag: str   # from the provided starter kit, else latest stable release
    sha: str


@dataclass
class Requirement:
    id: str           # "R1", "R2", ...
    text: str
    pivot: bool = False  # exactly one requirement per contract is the pivot


@dataclass
class Invocation:
    argv: list[str]
    env: dict[str, str] = field(default_factory=dict)
    input: str | None = None  # stdin, for prompts


@dataclass
class Outcome:
    exit_code: int
    output: str
    exception_type: str | None = None


@dataclass
class Seed:
    pair_id: str      # "<family>-<slug>", e.g. "conflict-format-flags"
    family: str       # one of FAMILIES in AGENTS.md
    feature: str      # one paragraph, shared by both twins
    policy_a: str
    policy_b: str
    reason_a: str     # stakeholder reason for policy A
    reason_b: str


@dataclass
class Contract:
    pair_id: str
    side: Side
    family: str
    requirements: list[Requirement]
    open_items: list[str]   # behaviour deliberately left unspecified
    public_api: str         # the signature(s) the feature adds, as text
    demo_app: str           # Python source of a tiny click app using the feature; must define `cli`
    grammar: dict           # input grammar for differential search; format in AGENTS.md
    probe: Invocation       # pivot probe: exercises the pivot requirement

    def pivot(self) -> Requirement:
        (req,) = [r for r in self.requirements if r.pivot]
        return req

    def frozen_hash(self) -> str:
        return hashlib.sha256(json.dumps(dataclasses.asdict(self), sort_keys=True).encode()).hexdigest()


@dataclass
class Assertion:
    """A ticket-derived semantic expectation about one Outcome."""
    requirement_id: str
    description: str
    python: str  # boolean expression over `outcome`, e.g. "outcome.exit_code == 2"


@dataclass
class Patch:
    path: str  # path to a unified diff against RepoPin.sha
    kind: PatchKind
    side: Side | None = None
    requirement_id: str | None = None  # for mutants: the requirement it violates
    model: str | None = None


@dataclass
class TestRun:
    passed: list[str]               # pytest node ids
    failed: dict[str, FailKind]     # node id -> why it failed
    log_path: str


@dataclass
class GateResult:
    gate: str  # "G0".."G9", "G6h"
    passed: bool
    detail: dict = field(default_factory=dict)


@dataclass
class Finding:
    """A lead from differential search. Never an expected value by itself."""
    invocation: Invocation
    outcome_a: Outcome
    outcome_b: Outcome
    label: FindingLabel | None = None
    replayed_fresh: bool = False


@dataclass
class Pair:
    seed: Seed
    pin: RepoPin
    contracts: dict[str, Contract] = field(default_factory=dict)       # "A"/"B"
    tickets: dict[str, str] = field(default_factory=dict)              # side -> Markdown
    references: dict[str, Patch] = field(default_factory=dict)
    graders: dict[str, str] = field(default_factory=dict)              # side -> test file path
    expectations: dict[str, list[Assertion]] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    gates: list[GateResult] = field(default_factory=list)
    status: PairStatus = "draft"
    reject_reason: str | None = None


# ---- JSON persistence -------------------------------------------------------

def save(obj, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(dataclasses.asdict(obj), indent=2, sort_keys=True))


def load(cls, path: str | Path):
    return _build(cls, json.loads(Path(path).read_text()))


def _build(tp, data):
    if data is None:
        return None
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        inner = [a for a in typing.get_args(tp) if a is not type(None)]
        return _build(inner[0], data)
    if origin is list:
        (item,) = typing.get_args(tp)
        return [_build(item, x) for x in data]
    if origin is dict:
        _, val = typing.get_args(tp)
        return {k: _build(val, v) for k, v in data.items()}
    if dataclasses.is_dataclass(tp):
        hints = typing.get_type_hints(tp)
        return tp(**{f.name: _build(hints[f.name], data[f.name]) for f in dataclasses.fields(tp) if f.name in data})
    return data


if __name__ == "__main__":
    import tempfile
    inv = Invocation(["--json", "--yaml"])
    c = Contract("p", "A", "conflict", [Requirement("R1", "x"), Requirement("R2", "y", pivot=True)],
                 [], "api", "src", {"options": []}, inv)
    pair = Pair(Seed("p", "conflict", "f", "a", "b", "ra", "rb"), RepoPin("pallets/click", "t", "s"),
                contracts={"A": c}, expectations={"A": [Assertion("R2", "d", "outcome.exit_code == 2")]},
                findings=[Finding(inv, Outcome(2, "e"), Outcome(0, "ok"))])
    with tempfile.TemporaryDirectory() as d:
        save(pair, f"{d}/pair.json")
        back = load(Pair, f"{d}/pair.json")
    assert back == pair, "round trip failed"
    assert back.contracts["A"].pivot().id == "R2"
    assert back.contracts["A"].frozen_hash() == c.frozen_hash()
    print("schema ok")

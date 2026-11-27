"""Pipeline orchestration with every stage faked (no Docker, no model)."""
from pathlib import Path

import pytest

from factory import pipeline
from factory.adapter_click import PIN
from factory.schema import Contract, Finding, GateResult, Invocation, Outcome, Pair, Patch, Requirement, Seed, load


def _contract(side: str) -> Contract:
    return Contract("conflict-fmt", side, "conflict",
                    [Requirement("R1", "accepted"), Requirement("R2", f"pivot {side}", pivot=True)],
                    ["wording"], "conflicts_with=", "import click\n", {"options": []}, Invocation(["--a", "--b"]))


class Fakes:
    """Records every stage call; gates pass unless a failure is queued for them."""

    def __init__(self, tmp: Path):
        self.tmp = tmp
        self.calls: list[str] = []
        self.fail_next: dict[str, list[GateResult]] = {}
        self.pair_json_seen: dict[str, bool] = {}
        self.raise_at: str | None = None
        self.value_error_at: set[str] = set()
        self.label = "pivot"

    def _rec(self, name: str):
        if self.raise_at == name:
            raise RuntimeError(f"killed at {name}")
        if name in self.value_error_at:
            self.calls.append(name)
            raise ValueError(f"{name} could not produce a valid result")
        self.calls.append(name)
        self.pair_json_seen[name] = (self.tmp / "runs" / "conflict-fmt" / "pair.json").exists()

    def _gate(self, gate: str, name: str):
        self._rec(name)
        queued = self.fail_next.get(name)
        return queued.pop(0) if queued else GateResult(gate, True, {})

    def lookup(self, stage: str):
        def _write(out, text="diff"):
            Path(out).parent.mkdir(parents=True, exist_ok=True)
            Path(out).write_text(text)

        table = {
            "surface": lambda pin: (self._rec("surface"), "surface map")[1],
            "seed": lambda surface, family, avoid: (self._rec("seed"),
                                                    Seed("conflict-fmt", family, "f", "a", "b", "ra", "rb"))[1],
            "novelty": lambda seed: self._gate("G8", "G8"),
            "realism": lambda seed, surface: self._gate("G9", "G9"),
            "contracts": lambda seed, surface: (self._rec("contracts"), (_contract("A"), _contract("B")))[1],
            "ticket": lambda c, seed: (self._rec("tickets"), f"ticket {c.side}")[1],
            "heldout": lambda ticket, pin, out_dir, n_wrong=3: (
                self._rec("heldout"), [Patch(str(Path(out_dir) / "w1.patch"), "heldout_wrong")])[1],
            "valid_alt": lambda ticket, pin, out: (self._rec("valid_alt"), Patch(str(out), "valid_alt"))[1],
            "reference": lambda c, ticket, pin, out: (self._rec("references"), _write(out),
                                                      Patch(str(out), "reference", side=c.side))[2],
            "repair_reference": lambda c, ticket, pin, patch, failure: (self._rec("repair_reference"), patch)[1],
            "expect": lambda ticket, probe, req: (self._rec("expectations"), [])[1],
            "grader": lambda c, ticket, assertions, out: (self._rec("graders"), _write(out, "def test_x(): pass\n"),
                                                          str(out))[2],
            "repair_grader": lambda c, ticket, path, failure, findings: (self._rec("repair_grader"), path)[1],
            "g1": lambda pair, side: self._gate("G1", "G1"),
            "g2": lambda pair, side: self._gate("G2", "G2"),
            "g3": lambda pair, side: self._gate("G3", "G3"),
            "g4": lambda path: self._gate("G4", "G4"),
            "g5": lambda pair: self._gate("G5", "G5"),
            "mutants": lambda c, ticket, ref, out_dir: (self._rec("mutants"), [Patch("m.patch", "mutant")])[1],
            "g6": lambda pair, side, mutants: self._gate("G6", "G6"),
            "g7": lambda pair, side, g6: self._gate("G7", "G7"),
            "g6h": lambda pair, side, patches: self._gate("G6h", "G6h"),
            "search": lambda pin, a, b, demo, grammar: (self._rec("search"),
                                                        [Finding(Invocation(["--a"]), Outcome(2, "x"), Outcome(0, "y"))])[1],
            "classify": lambda finding, ta, tb: (self._rec("classify"), self.label)[1],
            "blind_solve": lambda ticket, pin, model, out: (self._rec("blind_solve"), Patch(str(out), "solver", model=model))[1],
            "diagnose": lambda pair, side, patch: (self._rec("diagnose"), {"verdict": "pass"})[1],
        }
        return table[stage]


@pytest.fixture
def fakes(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path / "runs"))
    f = Fakes(tmp_path)
    monkeypatch.setattr(pipeline, "_fn", f.lookup)
    return f


def _first_seen(calls):
    out = []
    for c in calls:
        if c not in out:
            out.append(c)
    return out


def test_pipeline_order(fakes):
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "accepted", pair.reject_reason
    order = [c for c in _first_seen(fakes.calls) if c != "valid_alt"]
    assert order == ["surface", "seed", "G8", "G9", "contracts", "tickets", "heldout", "references",
                     "expectations", "graders", "G1", "G2", "G3", "G4", "G5", "search", "classify",
                     "mutants", "G6", "G7", "G6h"]
    assert fakes.calls.index("valid_alt") < fakes.calls.index("references")
    assert all(seen for stage, seen in fakes.pair_json_seen.items() if stage not in ("surface", "seed"))
    saved = load(Pair, Path(pipeline.run_dir("conflict-fmt")) / "pair.json")
    assert saved.status == "accepted" and {g.gate for g in saved.gates} >= {"G1", "G5", "G6h", "G8", "G9"}
    for side in "AB":
        assert (Path(pipeline.run_dir("conflict-fmt")) / "graders" / f"test_{side}.initial.py").exists()


@pytest.mark.parametrize("gate,detail,expected", [
    ("G2", {"suite_failed": ["tests/test_basic.py::t"], "grader_failed": {}}, "repair_reference"),
    ("G2", {"suite_failed": [], "grader_failed": {"x::test_new__R1__a": "assertion"}}, "repair_grader"),
    ("G1", {"new_passing_on_base": ["x"]}, "repair_grader"),
    ("G5", {"reason": "probe does not separate twins"}, "repair_grader"),
    ("G6", {"survivors": ["m.patch"]}, "repair_grader"),
])
def test_repair_routing(fakes, gate, detail, expected):
    fakes.fail_next[gate] = [GateResult(gate, False, detail)]
    pair = pipeline.run_pair("conflict", PIN)
    assert expected in fakes.calls
    other = {"repair_reference", "repair_grader"} - {expected}
    assert not other & set(fakes.calls)
    assert pair.status == "accepted"


def test_repair_gives_up_after_two(fakes):
    bad = GateResult("G5", False, {"reason": "probe does not separate twins"})
    fakes.fail_next["G5"] = [bad, bad, bad]
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected"
    assert pair.reject_reason.startswith("G5")
    assert fakes.calls.count("repair_grader") == 4  # 2 attempts x both graders


def test_g8_rejects_without_later_stages(fakes):
    fakes.fail_next["G8"] = [GateResult("G8", False, {"matches": ["envvar"]})]
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected" and pair.reject_reason.startswith("G8")
    assert "contracts" not in fakes.calls


def test_g6h_failure_rejects_without_repair(fakes):
    fakes.fail_next["G6h"] = [GateResult("G6h", False, {"reason": "valid alternative rejected"})]
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected" and pair.reject_reason.startswith("G6h")
    assert "repair_grader" not in fakes.calls


def test_resume(fakes):
    fakes.raise_at = "tickets"
    with pytest.raises(RuntimeError):
        pipeline.run_pair("conflict", PIN)
    fakes.raise_at = None
    before = list(fakes.calls)
    pair = pipeline.run_pair("conflict", PIN, pair_id="conflict-fmt")
    assert pair.status == "accepted"
    again = fakes.calls[len(before):]
    for stage in ("surface", "seed", "G8", "G9", "contracts"):
        assert stage not in again, stage


def test_finished_pair_is_not_regenerated(fakes):
    pipeline.run_pair("conflict", PIN)
    n = len(fakes.calls)
    assert pipeline.run_pair("conflict", PIN, pair_id="conflict-fmt").status == "accepted"
    assert len(fakes.calls) == n


def test_evaluate_pair(fakes):
    pipeline.run_pair("conflict", PIN)
    pipeline.evaluate_pair("conflict-fmt", ["claude-sonnet-5-5"])
    assert fakes.calls.count("blind_solve") == 2 and fakes.calls.count("diagnose") == 2
    state = pipeline.load_state("conflict-fmt")
    assert state["solver"]["claude-sonnet-5-5:A"]["diagnosis"] == {"verdict": "pass"}
    pipeline.evaluate_pair("conflict-fmt", ["claude-sonnet-5-5"])  # resumable: no repeat solves
    assert fakes.calls.count("blind_solve") == 2


def test_stage_table_points_at_owner_modules():
    owners = {"propose": "Akshat", "validate": "Urja", "evaluate": "Heet"}
    for stage, target in pipeline.STAGES.items():
        module = target.split(":")[0]
        assert module.startswith("factory."), target
        if module.split(".")[1] in owners or module == "factory.gates_basic":
            continue
        pytest.fail(f"{stage} -> {target} is not in an owner package")


def test_stage_value_error_rejects_pair(fakes):
    fakes.value_error_at = {"graders"}
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected" and pair.reject_reason.startswith("graders:")
    assert pipeline.run_pair("conflict", PIN, pair_id="conflict-fmt").status == "rejected"  # resume: stays rejected


def test_failed_repair_counts_as_attempt(fakes):
    bad = GateResult("G5", False, {"reason": "probe does not separate twins"})
    fakes.fail_next["G5"] = [bad, bad, bad]
    fakes.value_error_at = {"repair_grader"}
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected" and pair.reject_reason.startswith("G5")


def test_stale_gates_dropped_after_repair(fakes):
    ok2 = GateResult("G2", True, {})
    bad2 = GateResult("G2", False, {"grader_failed": {"x::test_new__R1__a": "assertion"}, "suite_failed": []})
    fakes.fail_next["G7"] = [GateResult("G7", False, {"untested": ["R1"]})]
    fakes.fail_next["G2"] = [ok2, ok2, bad2, bad2, bad2]
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected" and pair.reject_reason.startswith("G2")
    assert not {"G5", "G6", "G7"} & {g.gate for g in pair.gates}


def test_search_labels_findings(fakes):
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "accepted"
    assert [f.label for f in pair.findings] == ["pivot"]


def test_search_without_pivot_finding_rejects(fakes):
    fakes.label = "open"
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected"
    assert pair.reject_reason == "G5s: no distinguishing case found within budget"
    assert "repair_grader" not in fakes.calls


def test_search_shared_finding_repairs_references(fakes, monkeypatch):
    labels = iter(["shared", "pivot"])
    orig = fakes.lookup

    def lookup(stage):
        if stage == "classify":
            return lambda f, ta, tb: (fakes._rec("classify"), next(labels))[1]
        return orig(stage)

    monkeypatch.setattr(pipeline, "_fn", lookup)
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "accepted"
    assert fakes.calls.count("repair_reference") == 2  # both sides, one attempt


def test_g6h_records_both_sides(fakes):
    fakes.fail_next["G6h"] = [GateResult("G6h", False, {"reason": "valid alternative rejected"})]
    pair = pipeline.run_pair("conflict", PIN)
    assert pair.status == "rejected"
    assert sorted(g.detail["side"] for g in pair.gates if g.gate == "G6h") == ["A", "B"]

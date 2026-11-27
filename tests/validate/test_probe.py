"""G5 with a fake worker and a fake sandbox (no Docker)."""
import pytest

from factory import sandbox, worker
from factory.schema import Outcome, TestRun
from factory.validate import probe

OUT_A = Outcome(2, "Error: --json conflicts with --yaml\n")
OUT_B = Outcome(0, "fmt=yaml\n")


def grader_ids(path):
    import ast
    from pathlib import Path
    names = [n.name for n in ast.parse(Path(path).read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name.startswith("test")]
    return [f"_feature_tests/{Path(path).name}::{n}" for n in names]


@pytest.fixture
def fakes(monkeypatch, pair):
    """Probe outcomes per reference, and cross-grade results computed from them."""
    state = {"outcomes": {"ref_A.patch": OUT_A, "ref_B.patch": OUT_B}, "runs": [],
             "cross_fail_kind": "assertion", "cross_passes": set()}

    def fresh_call(pin, patch, demo_app, inv):
        assert inv.argv == ["--json", "--yaml"]
        return state["outcomes"][patch]

    def run_tests(pin, patches, test_files=None, repeat=1, pair_id=None, timeout=900):
        [ref], [grader_file] = patches, test_files
        state["runs"].append((ref, grader_file))
        ids = grader_ids(grader_file)
        own = ref.endswith(f"{grader_file[-4]}.patch")  # ref_A.patch with test_A.py
        if own or (ref, grader_file) in state["cross_passes"]:
            return TestRun(ids, {}, "log")
        pivot = [t for t in ids if "test_new__R4__" in t]
        return TestRun([t for t in ids if t not in pivot], {t: state["cross_fail_kind"] for t in pivot}, "log")

    monkeypatch.setattr(worker, "fresh_call", fresh_call)
    monkeypatch.setattr(sandbox, "run_tests", run_tests)
    return state


def test_g5_golden_passes(fakes, pair):
    g = probe.g5_twin_separation(pair)
    assert g.gate == "G5" and g.passed, g.detail
    assert g.detail["outcomes"]["A"]["exit_code"] == 2
    assert g.detail["outcomes"]["B"]["output"] == "fmt=yaml\n"
    assert g.detail["own"] == {"A": True, "B": True}
    assert g.detail["twin"] == {"A": False, "B": False}
    assert sorted(fakes["runs"]) == sorted([("ref_A.patch", pair.graders["B"]), ("ref_B.patch", pair.graders["A"])])


def test_g5_same_behaviour_fails(fakes, pair):
    fakes["outcomes"]["ref_B.patch"] = Outcome(2, "Error: --json conflicts with --yaml\n")
    g = probe.g5_twin_separation(pair)
    assert not g.passed
    assert g.detail["reason"] == "probe does not separate twins"
    assert fakes["runs"] == []  # no cross-grade when the probe already fails


def test_g5_ref_misses_own_ticket(fakes, pair):
    fakes["outcomes"]["ref_A.patch"] = Outcome(2, "Error: conflicting options\n")  # doesn't name both
    g = probe.g5_twin_separation(pair)
    assert not g.passed
    assert "A" in g.detail["reason"] and "own" in g.detail["reason"]


def test_g5_both_satisfy_a_pivot_assertion_fails(fakes, pair):
    """Review focus 3: if both references satisfy the twin's pivot assertions, the probe separates nothing."""
    pair.expectations["B"] = [pair.expectations["B"][0].__class__("R4", "anything", "outcome.exit_code >= 0")]
    g = probe.g5_twin_separation(pair)
    assert not g.passed


def test_g5_cross_grade(fakes, pair):
    fakes["cross_passes"].add(("ref_A.patch", pair.graders["B"]))
    g = probe.g5_twin_separation(pair)
    assert not g.passed
    assert "ref A passes grader B" in g.detail["reason"]


def test_g5_cross_grade_needs_assertion_failure(fakes, pair):
    fakes["cross_fail_kind"] = "error"
    g = probe.g5_twin_separation(pair)
    assert not g.passed
    assert "assertion" in g.detail["reason"]


def test_g5_grader_without_probe_test(fakes, pair, tmp_path):
    src = open(pair.graders["A"]).read().replace("test_new__R4__pivot_probe", "test_new__R4__other")
    (tmp_path / "test_A.py").write_text(src)
    g = probe.g5_twin_separation(pair)
    assert not g.passed
    assert "pivot_probe" in g.detail["reason"]

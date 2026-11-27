"""G6 mutants and G7 traceability, with a fake model and a fake sandbox (no Docker)."""
import pytest

from factory import sandbox
from factory.schema import GateResult, Patch, TestRun
from factory.validate import mutants, trace

DIFF = """--- a/src/click/core.py
+++ b/src/click/core.py
@@ -1,3 +1,3 @@
-old
+new
"""


def fenced_diff(req: str) -> str:
    return f"Here it is.\n\n```diff\n{DIFF.replace('new', 'new ' + req)}```\n"


# ---- make_mutants ------------------------------------------------------------

def test_one_mutant_per_requirement(fake_llm, tmp_path, contract_a):
    ref = tmp_path / "ref_A.patch"
    ref.write_text(DIFF)
    fake_llm["replies"] = [fenced_diff(r.id) for r in contract_a.requirements]
    got = mutants.make_mutants(contract_a, "the ticket", Patch(str(ref), "reference", side="A"), tmp_path / "m")
    assert [p.requirement_id for p in got] == ["R1", "R2", "R3", "R4"]
    assert all(p.kind == "mutant" and p.side == "A" and p.model for p in got)
    for p in got:
        text = open(p.path).read()
        assert text.startswith("--- a/") and f"new {p.requirement_id}" in text
    # Each prompt targets exactly one requirement and includes the reference.
    for prompt, r in zip(fake_llm["prompts"], contract_a.requirements):
        assert r.text in prompt and DIFF in prompt and "the ticket" in prompt


def test_mutant_retries_non_diff(fake_llm, tmp_path, contract_a):
    contract_a.requirements = contract_a.requirements[:1]
    ref = tmp_path / "ref.patch"
    ref.write_text(DIFF)
    fake_llm["replies"] = ["I can't write that", fenced_diff("R1")]
    [p] = mutants.make_mutants(contract_a, "t", Patch(str(ref), "reference", side="A"), tmp_path / "m")
    assert p.requirement_id == "R1"
    assert len(fake_llm["prompts"]) == 2


def test_mutant_skipped_after_retries(fake_llm, tmp_path, contract_a):
    contract_a.requirements = contract_a.requirements[:1]
    ref = tmp_path / "ref.patch"
    ref.write_text(DIFF)
    fake_llm["replies"] = ["no", "no", "no"]
    assert mutants.make_mutants(contract_a, "t", Patch(str(ref), "reference", side="A"), tmp_path / "m") == []


# ---- g6_mutants --------------------------------------------------------------

def mutant(req, path=None):
    return Patch(path or f"m_{req}.patch", "mutant", side="A", requirement_id=req)


@pytest.fixture
def fake_runs(monkeypatch):
    """Map mutant path -> TestRun returned by the grader run."""
    results = {}

    def run_tests(pin, patches, test_files=None, repeat=1, pair_id=None, timeout=900):
        [m] = patches
        return results[m]

    monkeypatch.setattr(sandbox, "run_tests", run_tests)
    return results


T = "_feature_tests/test_A.py::"


def test_g6_all_killed(fake_runs, pair):
    fake_runs.update({
        "m_R1.patch": TestRun([], {T + "test_new__R1__x": "missing_api"}, "l"),
        "m_R4.patch": TestRun([T + "test_new__R1__x"], {T + "test_new__R4__pivot_probe": "assertion"}, "l"),
    })
    g = mutants.g6_mutants(pair, "A", [mutant("R1"), mutant("R4")])
    assert g.gate == "G6" and g.passed
    assert g.detail["killed"] == {"m_R1.patch": [T + "test_new__R1__x"],
                                  "m_R4.patch": [T + "test_new__R4__pivot_probe"]}
    assert g.detail["survivors"] == []
    assert g.detail["mutant_requirements"] == {"m_R1.patch": "R1", "m_R4.patch": "R4"}


def test_g6_survivor_reported(fake_runs, pair):
    fake_runs.update({
        "m_R1.patch": TestRun([], {T + "test_new__R1__x": "assertion"}, "l"),
        "m_R3.patch": TestRun([T + "test_new__R1__x", T + "test_new__R3__y"], {}, "l"),
    })
    g = mutants.g6_mutants(pair, "A", [mutant("R1"), mutant("R3")])
    assert not g.passed
    assert g.detail["survivors"] == ["m_R3.patch"]


def test_g6_errors_are_not_kills(fake_runs, pair):
    """A mutant that doesn't apply or crashes everything is invalid, not killed."""
    fake_runs["m_R2.patch"] = TestRun([], {"_feature_tests/test_A.py": "error"}, "l")
    g = mutants.g6_mutants(pair, "A", [mutant("R2")])
    assert g.detail["killed"] == {} and g.detail["survivors"] == []
    assert g.detail["invalid"] == ["m_R2.patch"]
    assert not g.passed  # nothing was actually killed


def test_g6_no_mutants_fails(fake_runs, pair):
    assert not mutants.g6_mutants(pair, "A", []).passed


# ---- g7_trace ----------------------------------------------------------------

def g6_result(kills: dict[str, str]) -> GateResult:
    return GateResult("G6", True, {"killed": {p: ["t"] for p in kills}, "survivors": [],
                                   "mutant_requirements": kills})


def test_g7_passes(pair):
    g = trace.g7_trace(pair, "A", g6_result({"m1": "R1", "m2": "R2", "m3": "R3", "m4": "R4"}))
    assert g.gate == "G7" and g.passed, g.detail
    assert g.detail["requirements"]["R4"]["killed_mutants"] == ["m4"]
    assert any("pivot_probe" in t for t in g.detail["requirements"]["R4"]["tests"])


def test_g7_requirement_without_test(pair, tmp_path):
    src = open(pair.graders["A"]).read()
    src = src.replace("test_new__R4__pivot_probe", "test_new__R3__pivot_probe")
    (tmp_path / "test_A.py").write_text(src)
    g = trace.g7_trace(pair, "A", g6_result({"m1": "R1", "m2": "R2", "m3": "R3"}))
    assert not g.passed
    assert "R4" in g.detail["missing_tests"] and "R4" in g.detail["missing_kills"]


def test_g7_requirement_without_killed_mutant(pair):
    g = trace.g7_trace(pair, "A", g6_result({"m1": "R1", "m2": "R2", "m4": "R4"}))
    assert not g.passed
    assert g.detail["missing_kills"] == ["R3"] and g.detail["missing_tests"] == []


def test_g7_uncited_test(pair, tmp_path):
    src = open(pair.graders["A"]).read() + "\n\ndef test_extra():\n    assert True\n"
    (tmp_path / "test_A.py").write_text(src)
    g = trace.g7_trace(pair, "A", g6_result({"m1": "R1", "m2": "R2", "m3": "R3", "m4": "R4"}))
    assert not g.passed
    assert g.detail["uncited_tests"] == ["test_extra"]

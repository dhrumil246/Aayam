from pathlib import Path

import pytest

from factory import gates_basic, sandbox
from factory.adapter_click import PIN
from factory.schema import Pair, Patch, RepoPin, Seed, TestRun

DATA = Path(__file__).parent / "data"
NEW = "_feature_tests/grader.py::test_new__R1__probe"
PRES = "_feature_tests/grader.py::test_preserved__R2__echo"


def _pair(ref=str(DATA / "probe_42.patch"), grader=str(DATA / "grader_probe.py")) -> Pair:
    return Pair(Seed("probe", "validation", "f", "a", "b", "ra", "rb"), PIN,
                references={"A": Patch(ref, "reference", side="A")}, graders={"A": grader})


def _fake(monkeypatch, base: TestRun, ref: TestRun, suite: TestRun | None = None):
    def run_tests(pin, patches, test_files=None, repeat=1, pair_id=None):
        if test_files is None:
            return suite or TestRun([], {}, "")
        return ref if patches else base
    monkeypatch.setattr(sandbox, "run_tests", run_tests)


def test_parse_test_name():
    assert gates_basic.parse_test_name("tests/x.py::test_new__R2_R4__foo") == ("new", ["R2", "R4"])
    assert gates_basic.parse_test_name("x.py::TestA::test_preserved__R1__bar[p-1]") == ("preserved", ["R1"])
    assert gates_basic.parse_test_name("x.py::test_something") == ("other", [])


def test_g1_passes(monkeypatch):
    _fake(monkeypatch, base=TestRun([PRES], {NEW: "missing_api"}, ""), ref=TestRun([NEW, PRES], {}, ""))
    assert gates_basic.g1_fail_before(_pair(), "A").passed


def test_g1_collection_error_fails_gate(monkeypatch):
    _fake(monkeypatch, base=TestRun([], {"_feature_tests/grader.py": "collection"}, ""), ref=TestRun([], {}, ""))
    g = gates_basic.g1_fail_before(_pair(), "A")
    assert not g.passed and g.detail["bad_failures"]


def test_g1_new_test_passing_on_base_fails_gate(monkeypatch):
    _fake(monkeypatch, base=TestRun([NEW, PRES], {}, ""), ref=TestRun([NEW, PRES], {}, ""))
    g = gates_basic.g1_fail_before(_pair(), "A")
    assert not g.passed and g.detail["new_passing_on_base"] == [NEW]


def test_g1_preserved_must_pass_on_base(monkeypatch):
    _fake(monkeypatch, base=TestRun([], {NEW: "assertion", PRES: "assertion"}, ""), ref=TestRun([], {}, ""))
    g = gates_basic.g1_fail_before(_pair(), "A")
    assert not g.passed and g.detail["preserved_failing_on_base"] == [PRES]


def test_g1_unnamed_test_fails_gate(monkeypatch):
    odd = "_feature_tests/grader.py::test_odd"
    _fake(monkeypatch, base=TestRun([PRES, odd], {NEW: "assertion"}, ""), ref=TestRun([], {}, ""))
    g = gates_basic.g1_fail_before(_pair(), "A")
    assert not g.passed and g.detail["unnamed"] == [odd]


def test_g2_needs_grader_and_suite(monkeypatch):
    _fake(monkeypatch, base=TestRun([], {}, ""), ref=TestRun([NEW, PRES], {}, ""),
          suite=TestRun([], {"tests/test_basic.py::t": "assertion"}, ""))
    g = gates_basic.g2_pass_after(_pair(), "A")
    assert not g.passed and g.detail["suite_failed"] == ["tests/test_basic.py::t"]


def test_g3_detects_flip(monkeypatch):
    ok, bad = TestRun([NEW], {}, ""), TestRun([], {NEW: "assertion"}, "")
    runs = iter([ok, ok, bad, ok])  # calls go base, ref, base, ref: base flips
    monkeypatch.setattr(sandbox, "run_tests", lambda *a, **k: next(runs))
    g = gates_basic.g3_stability(_pair(), "A", n=2)
    assert not g.passed


def test_g4_rejects_private(tmp_path):
    for src in ["from click._compat import x\n", "import click._termui_impl\n",
                "import click\nclick._utils.f()\n", "from click.core import _private\n"]:
        (tmp_path / "t.py").write_text(src)
        assert not gates_basic.g4_public_api(str(tmp_path / "t.py")).passed, src


def test_g4_accepts_public(tmp_path):
    (tmp_path / "t.py").write_text("import click\nfrom click.testing import CliRunner\nclick.echo(click.__name__)\n")
    assert gates_basic.g4_public_api(str(tmp_path / "t.py")).passed


@pytest.mark.docker
def test_gates_on_probe_pair():
    pair = _pair()
    for gate in (gates_basic.g1_fail_before, gates_basic.g2_pass_after):
        g = gate(pair, "A")
        assert g.passed, (g.gate, g.detail)
    assert gates_basic.g3_stability(pair, "A", n=2).passed
    assert gates_basic.g4_public_api(pair.graders["A"]).passed
    wrong = _pair(ref=str(DATA / "probe_41.patch"))
    assert not gates_basic.g2_pass_after(wrong, "A").passed


def test_g1_unnamed_failing_test_fails_gate(monkeypatch):
    odd = "_feature_tests/grader.py::test_odd"
    _fake(monkeypatch, base=TestRun([PRES], {NEW: "assertion", odd: "assertion"}, ""), ref=TestRun([], {}, ""))
    g = gates_basic.g1_fail_before(_pair(), "A")
    assert not g.passed and g.detail["unnamed"] == [odd]

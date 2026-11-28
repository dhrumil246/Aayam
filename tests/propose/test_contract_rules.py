"""Unit tests for deterministic contract validation rules."""
import copy
from pathlib import Path

from factory.propose.contract import validate_contracts
from factory.schema import Contract, Invocation, Requirement, load

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"


def _golden() -> tuple[Contract, Contract]:
    return load(Contract, GOLDEN / "contract_A.json"), load(Contract, GOLDEN / "contract_B.json")


def test_golden_contracts_valid():
    a, b = _golden()
    assert validate_contracts(a, b) == []


def test_two_pivots_rejected():
    a, b = _golden()
    a_bad = copy.deepcopy(a)
    a_bad.requirements[0].pivot = True
    errs = validate_contracts(a_bad, b)
    assert any("pivot" in e for e in errs)


def test_shared_text_mismatch_rejected():
    a, b = _golden()
    b_bad = copy.deepcopy(b)
    b_bad.requirements[0].text = "Different shared text."
    errs = validate_contracts(a, b_bad)
    assert any("shared" in e for e in errs)


def test_demo_app_mismatch_rejected():
    a, b = _golden()
    b_bad = copy.deepcopy(b)
    b_bad.demo_app = a.demo_app + "\n# extra\n"
    errs = validate_contracts(a, b_bad)
    assert any("demo_app" in e for e in errs)


def test_probe_not_in_grammar_rejected():
    a, b = _golden()
    a_bad = copy.deepcopy(a)
    b_bad = copy.deepcopy(b)
    a_bad.probe = Invocation(["--unknown"])
    b_bad.probe = Invocation(["--unknown"])
    errs = validate_contracts(a_bad, b_bad)
    assert any("grammar" in e for e in errs)


def test_demo_app_without_cli_rejected():
    a, b = _golden()
    a_bad = copy.deepcopy(a)
    b_bad = copy.deepcopy(b)
    a_bad.demo_app = "import click\ndef not_cli(): pass\n"
    b_bad.demo_app = a_bad.demo_app
    errs = validate_contracts(a_bad, b_bad)
    assert any("cli" in e for e in errs)


def test_wording_only_pivot_rejected():
    a, b = _golden()
    a_bad = copy.deepcopy(a)
    b_bad = copy.deepcopy(b)
    a_bad.requirements[-1] = Requirement("R4", "Combining options raises usage error: cannot combine.", pivot=True)
    b_bad.requirements[-1] = Requirement("R4", "Combining options raises usage error: conflicts.", pivot=True)
    errs = validate_contracts(a_bad, b_bad)
    assert any("wording" in e for e in errs)

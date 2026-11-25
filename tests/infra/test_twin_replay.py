"""Model-free twin replay (decision D-2). Skips until fixtures/golden/ is committed."""
import hashlib
from pathlib import Path

import pytest

from factory import llm
from factory.adapter_click import PIN
from factory.gates_basic import parse_test_name
from factory.schema import Contract, load
from factory.sandbox import run_tests
from factory.worker import fresh_call

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"
NEEDED = ["contract_A.json", "contract_B.json", "ref_A.patch", "ref_B.patch", "graders/test_A.py", "graders/test_B.py"]

pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not all((GOLDEN / n).exists() for n in NEEDED), reason="golden pair not committed yet"),
]


def _no_models(monkeypatch):
    monkeypatch.delenv("FACTORY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("FACTORY_OFFLINE", "1")

    def boom(*a, **k):
        raise AssertionError("twin replay must not call a model")

    monkeypatch.setattr(llm, "_call", boom)


@pytest.mark.parametrize("side,twin", [("A", "B"), ("B", "A")])
def test_twin_replay_no_key(monkeypatch, side, twin):
    _no_models(monkeypatch)
    twin_pivot = load(Contract, GOLDEN / f"contract_{twin}.json").pivot().id
    ref = str(GOLDEN / f"ref_{side}.patch")

    own = run_tests(PIN, [ref], [str(GOLDEN / "graders" / f"test_{side}.py")])
    assert own.failed == {}, own.failed

    cross = run_tests(PIN, [ref], [str(GOLDEN / "graders" / f"test_{twin}.py")])
    on_pivot = {t: k for t, k in cross.failed.items()
                if parse_test_name(t)[0] == "new" and twin_pivot in parse_test_name(t)[1]}
    assert on_pivot, f"ref {side} passed every {twin_pivot} test of grader {twin}: {cross.failed}"
    assert set(on_pivot.values()) == {"assertion"}, on_pivot


def test_probe_outcomes_differ(monkeypatch):
    _no_models(monkeypatch)
    a = load(Contract, GOLDEN / "contract_A.json")
    out_a = fresh_call(PIN, str(GOLDEN / "ref_A.patch"), a.demo_app, a.probe)
    out_b = fresh_call(PIN, str(GOLDEN / "ref_B.patch"), a.demo_app, a.probe)
    assert out_a != out_b


def test_reference_patches_differ():
    digest = lambda n: hashlib.sha256((GOLDEN / n).read_bytes()).hexdigest()
    assert digest("ref_A.patch") != digest("ref_B.patch")

import json

import pytest
from hypothesis import given, settings

from factory import llm
from factory.schema import Finding, Invocation, Outcome, RepoPin
from factory.validate import search

PIN = RepoPin("pallets/click", "t", "s")
DEMO = "cli = None"

GRAMMAR = {
    "options": [
        {"flag": "--json", "kind": "flag"},
        {"flag": "--yaml", "kind": "flag"},
        {"flag": "--verbose", "kind": "flag"},          # noise
        {"flag": "--name", "kind": "value", "values": ["a", "b", ""]},  # noise
    ],
    "args": [{"name": "files", "values": ["x.txt", "y.txt"], "max": 2}],
    "env": {"APP_FORMAT": ["json", "yaml"]},
    "stdin": ["", "y\n"],
    "max_tokens": 6,
}


def conflict_errors(inv: Invocation) -> Outcome:
    if "--json" in inv.argv and "--yaml" in inv.argv:
        return Outcome(2, "Error: --json conflicts with --yaml\n")
    return Outcome(0, "ok\n")


def never_errors(inv: Invocation) -> Outcome:
    return Outcome(0, "ok\n")


def trailing_spaces(inv: Invocation) -> Outcome:
    return Outcome(0, "ok   \n\n")


@pytest.fixture
def fake_workers(monkeypatch):
    """Patches are names of plain functions; no Docker involved."""
    funcs = {"a": conflict_errors, "b": never_errors, "spaces": trailing_spaces}
    calls = {"persistent": 0, "fresh": 0}

    class FakeWorker:
        def __init__(self, pin, patch, demo_app):
            self.fn = funcs[patch]

        def call(self, inv, timeout=10.0):
            calls["persistent"] += 1
            return self.fn(inv)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            pass

    def fresh_call(pin, patch, demo_app, inv):
        calls["fresh"] += 1
        return funcs[patch](inv)

    monkeypatch.setattr(search, "Worker", FakeWorker)
    monkeypatch.setattr(search, "fresh_call", fresh_call)
    return funcs, calls


# ---- invocations ------------------------------------------------------------

def _allowed_tokens(grammar):
    tokens = set()
    for opt in grammar["options"]:
        tokens.add(opt["flag"])
        tokens.update(opt.get("values", []))
    for arg in grammar.get("args", []):
        tokens.update(arg["values"])
    return tokens


def test_strategy_respects_grammar():
    allowed = _allowed_tokens(GRAMMAR)
    seen = []

    @settings(max_examples=200, database=None, deadline=None)
    @given(search.invocations(GRAMMAR))
    def check(inv):
        seen.append(inv)
        assert isinstance(inv, Invocation)
        assert len(inv.argv) <= GRAMMAR["max_tokens"]
        assert set(inv.argv) <= allowed
        assert sum(t in ("x.txt", "y.txt") for t in inv.argv) <= 2
        for name, value in inv.env.items():
            assert value in GRAMMAR["env"][name]
        assert inv.input in GRAMMAR["stdin"]

    check()
    assert len(seen) == 200


def test_value_options_keep_their_value():
    @settings(max_examples=200, database=None, deadline=None)
    @given(search.invocations(GRAMMAR))
    def check(inv):
        for i, tok in enumerate(inv.argv):
            if tok == "--name":
                assert i + 1 < len(inv.argv) and inv.argv[i + 1] in ("a", "b", "")

    check()


def test_strategy_minimal_grammar():
    @settings(max_examples=50, database=None, deadline=None)
    @given(search.invocations({"options": [{"flag": "--x", "kind": "flag"}]}))
    def check(inv):
        assert set(inv.argv) <= {"--x"} and inv.env == {} and inv.input is None

    check()


# ---- diff_search ------------------------------------------------------------

def test_finds_and_shrinks(fake_workers):
    [finding] = search.diff_search(PIN, "a", "b", DEMO, GRAMMAR, budget=300)
    assert sorted(finding.invocation.argv) == ["--json", "--yaml"]
    assert finding.invocation.env == {}
    assert finding.outcome_a.exit_code == 2 and finding.outcome_b.exit_code == 0
    assert finding.replayed_fresh is True
    assert finding.label is None


def test_normalises_whitespace(fake_workers):
    assert search.diff_search(PIN, "b", "spaces", DEMO, GRAMMAR, budget=50) == []


def test_budget_exhausted(fake_workers):
    _, calls = fake_workers
    assert search.diff_search(PIN, "b", "b", DEMO, GRAMMAR, budget=30) == []
    assert calls["fresh"] == 0


def test_not_reproduced_dropped(fake_workers, monkeypatch):
    funcs, _ = fake_workers
    monkeypatch.setattr(search, "fresh_call", lambda pin, patch, demo, inv: never_errors(inv))
    assert search.diff_search(PIN, "a", "b", DEMO, GRAMMAR, budget=300) == []


def test_same_outcome():
    assert search.same_outcome(Outcome(0, "a  \nb\n\n"), Outcome(0, "a\nb"))
    assert not search.same_outcome(Outcome(0, "a"), Outcome(1, "a"))
    assert not search.same_outcome(Outcome(0, "a"), Outcome(0, "a", "ValueError"))
    assert not search.same_outcome(Outcome(0, " a"), Outcome(0, "a"))


# ---- classify_finding -------------------------------------------------------

TICKET_A = "R4: combining --json and --yaml is a usage error (exit 2) naming both options."
TICKET_B = "R4: when --json and --yaml are combined, the one that appears last wins."
FINDING = Finding(Invocation(["--json", "--yaml"]),
                  Outcome(2, "Error: --json conflicts with --yaml"), Outcome(0, "fmt=yaml"))


@pytest.fixture
def fake_llm(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    monkeypatch.delenv("FACTORY_OFFLINE", raising=False)
    state = {"prompts": [], "replies": []}

    def _call(prompt, model):
        state["prompts"].append(prompt)
        return state["replies"].pop(0), 1, 1

    monkeypatch.setattr(llm, "_call", _call)
    return state


def test_classify_pivot(fake_llm):
    fake_llm["replies"] = [json.dumps({"label": "pivot", "reason": "R4 differs"})]
    assert search.classify_finding(FINDING, TICKET_A, TICKET_B) == "pivot"
    [prompt] = fake_llm["prompts"]
    assert TICKET_A in prompt and TICKET_B in prompt
    assert '"--json", "--yaml"' in prompt
    assert "fmt=yaml" in prompt


def test_classify_retries_bad_label(fake_llm):
    fake_llm["replies"] = [json.dumps({"label": "maybe"}), json.dumps({"label": "open"})]
    assert search.classify_finding(FINDING, TICKET_A, TICKET_B) == "open"
    assert "maybe" in fake_llm["prompts"][1]


def test_classify_gives_up(fake_llm):
    fake_llm["replies"] = [json.dumps({"label": "x"})] * 3
    with pytest.raises(ValueError):
        search.classify_finding(FINDING, TICKET_A, TICKET_B)

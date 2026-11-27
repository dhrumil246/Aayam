import json

import pytest

from factory import llm
from factory.schema import Assertion, Invocation, Outcome
from factory.validate import expect

TICKET_A = """# Let options declare conflicts

Add a `conflicts_with` parameter to `click.Option`.

- R4: Passing two options that conflict is a usage error (exit code 2). The error
  message names both options.
"""
TICKET_B_PIVOT = "the one that appears last on the command line wins"
PROBE = Invocation(["--json", "--yaml"])


def a(python: str) -> Assertion:
    return Assertion("R4", "d", python)


@pytest.fixture
def fake_llm(monkeypatch, tmp_path):
    """Replace the provider call; record prompts and serve queued replies."""
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    monkeypatch.delenv("FACTORY_OFFLINE", raising=False)

    class Fake:
        prompts: list[str] = []
        replies: list[str] = []

    def _call(prompt, model):
        Fake.prompts.append(prompt)
        return Fake.replies.pop(0), 1, 1

    Fake.prompts, Fake.replies = [], []
    monkeypatch.setattr(llm, "_call", _call)
    return Fake


# ---- check -----------------------------------------------------------------

def test_check_golden_a():
    assertions = [a("outcome.exit_code == 2"),
                  a("'--json' in outcome.output and '--yaml' in outcome.output")]
    good = expect.check(assertions, Outcome(2, "Error: --json conflicts with --yaml"))
    bad = expect.check(assertions, Outcome(0, "fmt=yaml"))
    assert [ok for _, ok in good] == [True, True]
    assert [ok for _, ok in bad] == [False, False]
    assert [x for x, _ in good] == assertions


def test_check_allowed_helpers():
    out = Outcome(2, "Error: Bad\n  two lines  \n", "UsageError")
    assertions = [a("len(outcome.output.splitlines()) == 2"),
                  a("outcome.output.lower().count('bad') == 1"),
                  a("outcome.output.find('Error') == 0"),
                  a("outcome.exception_type == 'UsageError'"),
                  a("outcome.exit_code in (1, 2) and not outcome.exit_code == 0")]
    assert all(ok for _, ok in expect.check(assertions, out))


def test_check_error_while_evaluating_is_false():
    # exception_type is None here, so .lower() raises: the outcome doesn't satisfy it.
    [(_, ok)] = expect.check([a("outcome.exception_type.lower() == 'usageerror'")], Outcome(0, "ok"))
    assert ok is False


def test_check_refuses_unvalidated():
    with pytest.raises(ValueError, match="__class__"):
        expect.check([a("outcome.__class__")], Outcome(0, ""))


# ---- validate_assertion ----------------------------------------------------

def test_validate_accepts_golden():
    assert expect.validate_assertion(a("outcome.exit_code == 2")) == []
    assert expect.validate_assertion(a("outcome.exception_type is None")) == []


def test_validate_rejects_dunder():
    assert expect.validate_assertion(a("outcome.__class__")) != []


def test_validate_rejects_call():
    errors = expect.validate_assertion(a("__import__('os')"))
    assert errors and any("__import__" in e for e in errors)


def test_validate_rejects_tautology():
    assert expect.validate_assertion(a("1 == 1")) != []


def test_validate_rejects_self_comparison():
    assert expect.validate_assertion(a("outcome.exit_code == outcome.exit_code")) != []


@pytest.mark.parametrize("python", [
    "outcome.output.replace('a', 'b') == 'b'",   # method not on the allow-list
    "outcome.output[0] == 'E'",                  # subscript
    "outcome.exit_code",                         # not a boolean check
    "[x for x in outcome.output]",               # comprehension
    "lambda: outcome",                           # lambda
    "open('f') is None",                         # builtin other than len
    "outcome.output.count(sep='x') == 1",        # keyword arguments
    "outcome.output is 'x'",                     # `is` only against None
    "other.exit_code == 2",                      # unknown name
    "outcome.exit_code ==",                      # syntax error
    "outcome.exit_code == 2; import os",         # statements
])
def test_validate_rejects(python):
    assert expect.validate_assertion(a(python)) != []


# ---- derive_expectations ---------------------------------------------------

REPLY = json.dumps([
    {"description": "usage error", "python": "outcome.exit_code == 2"},
    {"description": "names both", "python": "'--json' in outcome.output and '--yaml' in outcome.output"},
])


def test_derive_returns_assertions(fake_llm):
    fake_llm.replies = [REPLY]
    got = expect.derive_expectations(TICKET_A, PROBE, "R4")
    assert [x.python for x in got] == ["outcome.exit_code == 2",
                                      "'--json' in outcome.output and '--yaml' in outcome.output"]
    assert all(x.requirement_id == "R4" for x in got)


def test_derive_sees_only_ticket(fake_llm):
    fake_llm.replies = [REPLY]
    expect.derive_expectations(TICKET_A, PROBE, "R4")
    [prompt] = fake_llm.prompts
    assert TICKET_A in prompt
    assert '"--json", "--yaml"' in prompt
    lower = prompt.lower()
    for banned in ("pair_id", TICKET_B_PIVOT, "patch", "diff"):
        assert banned not in lower


def test_derive_retries_with_errors(fake_llm):
    fake_llm.replies = [json.dumps([{"description": "x", "python": "outcome.__class__"}]), REPLY]
    got = expect.derive_expectations(TICKET_A, PROBE, "R4")
    assert len(got) == 2
    assert "__class__" in fake_llm.prompts[1]


def test_derive_gives_up(fake_llm):
    bad = json.dumps([{"description": "x", "python": "1 == 1"}])
    fake_llm.replies = [bad, bad, bad]
    with pytest.raises(ValueError, match="R4"):
        expect.derive_expectations(TICKET_A, PROBE, "R4")
    assert len(fake_llm.prompts) == 3

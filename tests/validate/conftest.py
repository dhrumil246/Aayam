"""Shared fixtures for validate tests: a golden-like conflict contract built in code.

Replace with `schema.load(Contract, "fixtures/golden/contract_A.json")` once
Akshat's golden pair lands.
"""
from pathlib import Path

import pytest

from factory import llm
from factory.schema import Assertion, Contract, Invocation, Pair, Patch, RepoPin, Requirement, Seed

DEMO_APP = '''import click


@click.command()
@click.option("--json", "fmt", flag_value="json", conflicts_with=["yaml"])
@click.option("--yaml", "fmt", flag_value="yaml", conflicts_with=["json"])
def cli(fmt):
    click.echo(f"fmt={fmt}")
'''

PIVOT_A = "Combining options that conflict is a usage error (exit code 2) whose message names both options."
PIVOT_B = "When conflicting options are combined, the one that appears last on the command line wins."


def make_contract(side: str = "A") -> Contract:
    return Contract(
        pair_id="conflict-format-flags",
        side=side,
        family="conflict",
        requirements=[
            Requirement("R1", "`click.Option` and `click.option` accept a `conflicts_with` list of option names."),
            Requirement("R2", "Using only one of the conflicting options behaves exactly as today."),
            Requirement("R3", "Options not listed in `conflicts_with` are unaffected."),
            Requirement("R4", PIVOT_A if side == "A" else PIVOT_B, pivot=True),
        ],
        open_items=["exact error wording", "whether --help mentions the conflict"],
        public_api="click.Option(..., conflicts_with: list[str] | None = None)",
        demo_app=DEMO_APP,
        grammar={"options": [{"flag": "--json", "kind": "flag"}, {"flag": "--yaml", "kind": "flag"}]},
        probe=Invocation(["--json", "--yaml"]),
    )


@pytest.fixture
def contract_a() -> Contract:
    return make_contract("A")


GRADER_BODY = '''
def test_new__R1__option_accepts_conflicts_with():
    assert click.Option(["--a"], conflicts_with=["b"]).name == "a"


def test_preserved__R2__single_flag_still_works():
    @click.command()
    @click.option("--json", "fmt", flag_value="json")
    def plain(fmt):
        click.echo(f"fmt={fmt}")
    assert "fmt=json" in CliRunner().invoke(plain, ["--json"]).output


def test_new__R3__unlisted_options_unaffected():
    assert run([]).exit_code == 0
'''

EXPECT_A = [Assertion("R4", "usage error", "outcome.exit_code == 2"),
            Assertion("R4", "names both", "'--json' in outcome.output and '--yaml' in outcome.output")]
EXPECT_B = [Assertion("R4", "no error", "outcome.exit_code == 0"),
            Assertion("R4", "last wins", "'fmt=yaml' in outcome.output")]


def make_pair(tmp_path: Path) -> Pair:
    """A conflict twin pair with real grader files on disk and fake reference patch paths."""
    from factory.validate import grader

    contracts = {"A": make_contract("A"), "B": make_contract("B")}
    expectations = {"A": list(EXPECT_A), "B": list(EXPECT_B)}
    graders = {}
    for side, c in contracts.items():
        path = tmp_path / f"test_{side}.py"
        probe = grader.probe_test_source(expectations[side], c.probe, "R4")
        path.write_text(grader.assemble(c, GRADER_BODY, [probe]))
        graders[side] = str(path)
    return Pair(
        seed=Seed("conflict-format-flags", "conflict", "f", "error", "last wins", "ra", "rb"),
        pin=RepoPin("pallets/click", "8.5.1", "cf19179"),
        contracts=contracts,
        tickets={"A": "ticket A: " + PIVOT_A, "B": "ticket B: " + PIVOT_B},
        references={s: Patch(f"ref_{s}.patch", "reference", side=s) for s in ("A", "B")},
        graders=graders,
        expectations=expectations,
    )


@pytest.fixture
def pair(tmp_path) -> Pair:
    return make_pair(tmp_path)


@pytest.fixture
def fake_llm(monkeypatch, tmp_path):
    """Replace the provider call; record prompts and serve queued replies in order."""
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path / "runs"))
    monkeypatch.delenv("FACTORY_OFFLINE", raising=False)
    state = {"prompts": [], "replies": []}

    def _call(prompt, model):
        state["prompts"].append(prompt)
        return state["replies"].pop(0), 1, 1

    monkeypatch.setattr(llm, "_call", _call)
    return state

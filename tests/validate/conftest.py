"""Shared fixtures for validate tests: a golden-like conflict contract built in code.

Replace with `schema.load(Contract, "fixtures/golden/contract_A.json")` once
Akshat's golden pair lands.
"""
import pytest

from factory import llm
from factory.schema import Contract, Invocation, Requirement

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

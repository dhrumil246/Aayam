"""Unit tests for write_contracts."""
import copy
import dataclasses
from pathlib import Path

import pytest

from factory.propose import contract
from factory.schema import Contract, Seed, load

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"


def test_write_contracts_golden_roundtrip(monkeypatch):
    seed = load(Seed, GOLDEN / "seed.json")
    ga = load(Contract, GOLDEN / "contract_A.json")
    gb = load(Contract, GOLDEN / "contract_B.json")
    payload = {"A": dataclasses.asdict(ga), "B": dataclasses.asdict(gb)}

    monkeypatch.setattr(contract, "llm_json", lambda prompt, role, pair_id=None: payload)
    a, b = contract.write_contracts(seed, "surface")
    assert a == ga
    assert b == gb


def test_write_contracts_retries_and_rejects(monkeypatch):
    seed = load(Seed, GOLDEN / "seed.json")
    ga = load(Contract, GOLDEN / "contract_A.json")
    gb = load(Contract, GOLDEN / "contract_B.json")
    bad_a = copy.deepcopy(ga)
    bad_a.requirements[0].pivot = True  # two pivots
    bad_payload = {"A": dataclasses.asdict(bad_a), "B": dataclasses.asdict(gb)}

    prompts: list[str] = []

    def fake_llm_json(prompt, role, pair_id=None):
        prompts.append(prompt)
        return bad_payload

    monkeypatch.setattr(contract, "llm_json", fake_llm_json)
    with pytest.raises(ValueError, match="invalid contracts"):
        contract.write_contracts(seed, "surface")
    assert len(prompts) == 3
    assert "pivot" in prompts[1]

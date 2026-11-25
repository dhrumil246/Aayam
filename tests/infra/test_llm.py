import json

import pytest

from factory import llm


@pytest.fixture
def fake(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    monkeypatch.delenv("FACTORY_OFFLINE", raising=False)
    monkeypatch.delenv("FACTORY_PAIR_BUDGET_USD", raising=False)
    class Fake(list):
        reply = "hello"

    calls = Fake()

    def _call(prompt, model):
        calls.append(prompt)
        return calls.reply, 1000, 1000

    monkeypatch.setattr(llm, "_call", _call)
    return calls


def test_cache_hit_offline(fake, monkeypatch):
    assert llm.llm("p", role="seed") == "hello"
    monkeypatch.setenv("FACTORY_OFFLINE", "1")
    assert llm.llm("p", role="seed") == "hello"
    assert len(fake) == 1


def test_cache_miss_offline_raises(fake, monkeypatch):
    monkeypatch.setenv("FACTORY_OFFLINE", "1")
    with pytest.raises(llm.OfflineCacheMiss, match="seed"):
        llm.llm("never seen", role="seed", pair_id="p1")
    assert fake == []


def test_costs_logged(fake, tmp_path):
    llm.llm("p", role="seed", pair_id="p1")
    lines = (tmp_path / "costs.jsonl").read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert set(row) == {"ts", "role", "model", "pair_id", "in_tokens", "out_tokens", "usd"}
    assert row["pair_id"] == "p1" and row["usd"] > 0


def test_budget(fake, monkeypatch):
    monkeypatch.setenv("FACTORY_PAIR_BUDGET_USD", "0.0001")
    llm.llm("first", role="seed", pair_id="p1")
    with pytest.raises(llm.BudgetExceeded):
        llm.llm("second", role="seed", pair_id="p1")
    assert len(fake) == 1


def test_llm_json_fenced(fake):
    fake.reply = "```json\n{\"a\":1}\n```"
    assert llm.llm_json("p", role="seed") == {"a": 1}


def test_llm_json_retries_once(fake, monkeypatch):
    replies = iter(["not json", "[1, 2]"])
    monkeypatch.setattr(llm, "_call", lambda prompt, model: (next(replies), 1, 1))
    assert llm.llm_json("p", role="seed") == [1, 2]


def test_load_prompt(tmp_path, monkeypatch):
    (tmp_path / "prompts" / "propose").mkdir(parents=True)
    (tmp_path / "prompts" / "propose" / "seed.md").write_text("Family: {family}")
    monkeypatch.setattr(llm, "PROMPTS", tmp_path / "prompts")
    assert llm.load_prompt("propose", "seed", family="conflict") == "Family: conflict"


@pytest.mark.llm
def test_live_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    assert "4" in llm.llm("What is 2+2? Reply with the digit only.", role="smoke")

"""Unit tests for surface map discovery and seed proposal."""
import json

from factory import adapter_click
from factory.propose import seeds, surface
from factory.schema import RepoPin


def test_surface_lists_public_names(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    fake_repo = tmp_path / "click_repo"
    (fake_repo / "src" / "click").mkdir(parents=True)
    (fake_repo / "src" / "click" / "__init__.py").write_text(
        "from __future__ import annotations\n"
        "from .core import Option as Option\n"
        "from .decorators import command as command\n"
        "from .utils import echo as echo\n",
        encoding="utf-8",
    )
    (fake_repo / "src" / "click" / "core.py").write_text("class Option(Parameter):\n    pass\n", encoding="utf-8")

    monkeypatch.setattr(adapter_click, "repo_dir", lambda pin: fake_repo)
    monkeypatch.setattr(surface, "llm", lambda prompt, role: "Option extension summary.")

    pin = RepoPin("pallets/click", "8.5.1", "abc123def456")
    out = surface.discover_surface(pin)
    for name in ("Option", "command", "echo"):
        assert name in out
    assert "Option extension summary." in out


def test_surface_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    fake_repo = tmp_path / "click_repo"
    (fake_repo / "src" / "click").mkdir(parents=True)
    (fake_repo / "src" / "click" / "__init__.py").write_text("from .core import Option as Option\n", encoding="utf-8")
    (fake_repo / "src" / "click" / "core.py").write_text("class Option(Parameter):\n    pass\n", encoding="utf-8")

    monkeypatch.setattr(adapter_click, "repo_dir", lambda pin: fake_repo)
    calls = []
    monkeypatch.setattr(surface, "llm", lambda prompt, role: calls.append(role) or "Summary.")

    pin = RepoPin("pallets/click", "8.5.1", "deadbeef1234")
    first = surface.discover_surface(pin)
    second = surface.discover_surface(pin)
    assert first == second
    assert len(calls) == 1
    assert (tmp_path / "surface_deadbeef1234.md").exists()


def test_seed_has_family_and_reasons(monkeypatch):
    payload = {
        "pair_id": "precedence-env-default-map",
        "family": "precedence",
        "feature": "Add env_overrides_default_map on Option.",
        "policy_a": "Env var overrides default_map.",
        "policy_b": "default_map overrides env var.",
        "reason_a": "12-factor apps expect env vars to win.",
        "reason_b": "Per-command config should override global env.",
    }
    monkeypatch.setattr(seeds, "llm_json", lambda prompt, role: payload)
    seed = seeds.propose_seed("surface", "precedence", [])
    assert seed.family == "precedence"
    assert seed.reason_a
    assert seed.reason_b


def test_seed_avoids(monkeypatch):
    seen_prompts = []

    def fake_llm_json(prompt, role):
        seen_prompts.append(prompt)
        return {
            "pair_id": "conflict-alias",
            "family": "conflict",
            "feature": "Feature X.",
            "policy_a": "A",
            "policy_b": "B",
            "reason_a": "RA",
            "reason_b": "RB",
        }

    monkeypatch.setattr(seeds, "llm_json", fake_llm_json)
    seeds.propose_seed("surface", "conflict", ["conflicts_with"])
    assert len(seen_prompts) == 1
    assert "conflicts_with" in seen_prompts[0]

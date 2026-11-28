"""Unit tests for G8 novelty and G9 realism gates."""
from factory.propose import novelty, realism
from factory.schema import Seed


def _seed(feature: str = "Add envvar support to Option.") -> Seed:
    return Seed(
        pair_id="conflict-test",
        family="conflict",
        feature=feature,
        policy_a="Policy A",
        policy_b="Policy B",
        reason_a="Reason A",
        reason_b="Reason B",
    )


def test_novelty_rejects_existing(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    monkeypatch.setenv("FACTORY_OFFLINE", "1")
    fake_repo = tmp_path / "main_repo"
    (fake_repo / "src" / "click").mkdir(parents=True)
    (fake_repo / "src" / "click" / "core.py").write_text("class Parameter:\n    envvar: str | None\n", encoding="utf-8")
    monkeypatch.setattr(novelty, "_ensure_main_repo", lambda: fake_repo)

    def fake_llm_json(prompt, role, pair_id=None):
        if role == "novelty_terms":
            return {"terms": ["envvar"]}
        return {"already_exists": True, "reason": "envvar already exists in Parameter."}

    monkeypatch.setattr(novelty, "llm_json", fake_llm_json)
    res = novelty.novelty_gate(_seed())
    assert res.gate == "G8"
    assert res.passed is False
    assert res.detail["matches"]


def test_novelty_uses_synonyms(tmp_path, monkeypatch):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path))
    monkeypatch.setenv("FACTORY_OFFLINE", "1")
    fake_repo = tmp_path / "main_repo"
    (fake_repo / "src" / "click").mkdir(parents=True)
    (fake_repo / "src" / "click" / "core.py").write_text("class Option:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(novelty, "_ensure_main_repo", lambda: fake_repo)

    grepped_terms: list[str] = []
    orig_grep = novelty._grep_repo

    def spy_grep(repo, terms, limit_per_term=8):
        grepped_terms.extend(terms)
        return orig_grep(repo, terms, limit_per_term=limit_per_term)

    monkeypatch.setattr(novelty, "_grep_repo", spy_grep)

    def fake_llm_json(prompt, role, pair_id=None):
        if role == "novelty_terms":
            return {"terms": ["exclusive", "mutually"]}
        return {"already_exists": False, "reason": "No matches."}

    monkeypatch.setattr(novelty, "llm_json", fake_llm_json)
    res = novelty.novelty_gate(_seed("Add conflicts_with."))
    assert res.passed is True
    assert "exclusive" in grepped_terms
    assert "mutually" in grepped_terms


def test_realism_threshold(monkeypatch):
    monkeypatch.setattr(
        realism,
        "llm_json",
        lambda prompt, role, pair_id=None: {"fit": 5, "reason": 4, "usefulness": 3, "comment": "Good."},
    )
    ok = realism.realism_gate(_seed(), "surface")
    assert ok.gate == "G9"
    assert ok.passed is True
    assert ok.detail["mean"] == 4.0
    assert ok.detail["needs_human_signoff"] is True

    monkeypatch.setattr(
        realism,
        "llm_json",
        lambda prompt, role, pair_id=None: {"fit": 4, "reason": 4, "usefulness": 3, "comment": "Weak."},
    )
    fail = realism.realism_gate(_seed(), "surface")
    assert fail.passed is False
    assert fail.detail["mean"] == 3.67

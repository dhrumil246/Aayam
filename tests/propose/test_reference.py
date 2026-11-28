"""Unit tests for write_reference and repair_reference."""
from pathlib import Path

from factory import adapter_click, sandbox, worker
from factory.propose import reference
from factory.schema import Contract, Outcome, TestRun, load

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"


def _fake_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "click_repo"
    (repo / "src" / "click").mkdir(parents=True)
    (repo / "src" / "click" / "core.py").write_text("class Option:\n    pass\n", encoding="utf-8")
    return repo


def _good_diff() -> str:
    return (
        "--- a/src/click/core.py\n"
        "+++ b/src/click/core.py\n"
        "@@ -1 +1,2 @@\n"
        " class Option:\n"
        "+    # patched\n"
        "     pass\n"
    )


def test_rejects_patch_touching_tests(tmp_path, monkeypatch):
    contract_a = load(Contract, GOLDEN / "contract_A.json")
    ticket_a = (GOLDEN / "ticket_A.md").read_text(encoding="utf-8")
    repo = _fake_repo(tmp_path)
    monkeypatch.setattr(adapter_click, "repo_dir", lambda pin: repo)
    monkeypatch.setattr(reference, "llm_json", lambda p, role, pair_id=None: {"files": ["src/click/core.py"]})

    bad_diff = "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n@@ -1 +1 @@\n-a\n+b\n"
    replies = iter([bad_diff, _good_diff()])
    monkeypatch.setattr(reference, "llm", lambda p, role, pair_id=None: next(replies))
    monkeypatch.setattr(sandbox, "apply_check", lambda pin, p: (True, ""))
    monkeypatch.setattr(sandbox, "run_tests", lambda pin, ps, pair_id=None: TestRun(["t1"], {}, "log"))
    monkeypatch.setattr(worker, "fresh_call", lambda pin, p, app, inv: Outcome(2, "error"))

    out = tmp_path / "ref_A.patch"
    patch = reference.write_reference(contract_a, ticket_a, adapter_click.PIN, out)
    assert patch.kind == "reference"
    assert "tests/" not in out.read_text(encoding="utf-8")


def test_iterates_on_apply_failure(tmp_path, monkeypatch):
    contract_a = load(Contract, GOLDEN / "contract_A.json")
    ticket_a = (GOLDEN / "ticket_A.md").read_text(encoding="utf-8")
    repo = _fake_repo(tmp_path)
    monkeypatch.setattr(adapter_click, "repo_dir", lambda pin: repo)
    monkeypatch.setattr(reference, "llm_json", lambda p, role, pair_id=None: {"files": ["src/click/core.py"]})

    prompts: list[str] = []

    def fake_llm(prompt, role, pair_id=None):
        prompts.append(prompt)
        return _good_diff()

    apply_results = iter([(False, "hunk #1 FAILED"), (True, "")])
    monkeypatch.setattr(reference, "llm", fake_llm)
    monkeypatch.setattr(sandbox, "apply_check", lambda pin, p: next(apply_results))
    monkeypatch.setattr(sandbox, "run_tests", lambda pin, ps, pair_id=None: TestRun(["t1"], {}, "log"))
    monkeypatch.setattr(worker, "fresh_call", lambda pin, p, app, inv: Outcome(2, "error"))

    out = tmp_path / "ref_A.patch"
    reference.write_reference(contract_a, ticket_a, adapter_click.PIN, out)
    assert len(prompts) == 2
    assert "hunk #1 FAILED" in prompts[1]


def test_smoke_probe_no_crash(tmp_path, monkeypatch):
    contract_a = load(Contract, GOLDEN / "contract_A.json")
    ticket_a = (GOLDEN / "ticket_A.md").read_text(encoding="utf-8")
    repo = _fake_repo(tmp_path)
    monkeypatch.setattr(adapter_click, "repo_dir", lambda pin: repo)
    monkeypatch.setattr(reference, "llm_json", lambda p, role, pair_id=None: {"files": ["src/click/core.py"]})

    prompts: list[str] = []
    monkeypatch.setattr(reference, "llm", lambda p, role, pair_id=None: prompts.append(p) or _good_diff())
    monkeypatch.setattr(sandbox, "apply_check", lambda pin, p: (True, ""))
    monkeypatch.setattr(sandbox, "run_tests", lambda pin, ps, pair_id=None: TestRun(["t1"], {}, "log"))

    outcomes = iter([Outcome(1, "boom", "TypeError"), Outcome(2, "usage error", "SystemExit")])
    monkeypatch.setattr(worker, "fresh_call", lambda pin, p, app, inv: next(outcomes))

    out = tmp_path / "ref_A.patch"
    reference.write_reference(contract_a, ticket_a, adapter_click.PIN, out)
    assert len(prompts) == 2
    assert "TypeError" in prompts[1]

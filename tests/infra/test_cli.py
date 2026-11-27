import subprocess
import sys
from pathlib import Path

import pytest

from factory import cli, pipeline
from factory.adapter_click import PIN
from factory.schema import Pair, Seed, save

ROOT = Path(__file__).resolve().parents[2]


def test_cli_help_lists_commands():
    out = subprocess.run([sys.executable, "-m", "factory", "--help"], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0
    for cmd in ("generate", "evaluate", "export", "report", "replay"):
        assert cmd in out.stdout


def test_generate_calls_run_pair(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(pipeline, "run_pair", lambda family, pin, pair_id=None: (
        calls.append((family, pin, pair_id)), Pair(Seed(f"{family}-x", family, "f", "a", "b", "r", "r"), pin,
                                                  status="accepted"))[1])
    assert cli.main(["generate", "--family", "conflict", "--n", "2"]) == 0
    assert calls == [("conflict", PIN, None)] * 2
    assert "accepted" in capsys.readouterr().out


def test_generate_rejects_unknown_family():
    with pytest.raises(SystemExit):
        cli.main(["generate", "--family", "nonsense"])


def test_evaluate_passes_models(monkeypatch):
    seen = []
    monkeypatch.setattr(pipeline, "evaluate_pair", lambda pid, models: seen.append((pid, models)))
    assert cli.main(["evaluate", "p1", "--models", "m1,m2"]) == 0
    assert seen == [("p1", ["m1", "m2"])]


def test_export_all_only_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("FACTORY_RUNS", str(tmp_path / "runs"))
    for pid, status in (("a-1", "accepted"), ("b-1", "rejected")):
        save(Pair(Seed(pid, "conflict", "f", "a", "b", "r", "r"), PIN, status=status), tmp_path / "runs" / pid / "pair.json")
    exported = []
    monkeypatch.setattr(cli, "_heet", lambda name: (lambda pair, out_dir: exported.append(pair.seed.pair_id) or []))
    assert cli.main(["export", "--all", "--out", str(tmp_path / "pk")]) == 0
    assert exported == ["a-1"]


def test_replay_exit_code(monkeypatch):
    monkeypatch.setattr(cli, "_heet", lambda name: (lambda pkg: {"matches": False, "diffs": ["probe.json"]}))
    assert cli.main(["replay", "packages/x"]) == 1

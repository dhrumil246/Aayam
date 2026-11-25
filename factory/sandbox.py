"""Run pytest against a (patched) click checkout inside Docker. Owner: Dhrumil."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from factory import adapter_click
from factory.schema import RepoPin, TestRun

PLUGIN_DIR = adapter_click.ROOT / "docker"


def _run_pytest(pin: RepoPin, workdir: Path | None, args: list[str], timeout: int = 900) -> tuple[list[dict], str]:
    """Run `pytest <args>` in the pinned image with the network off.

    workdir, if given, is a patched click checkout mounted over /work/click.
    Returns (report rows from docker/report_plugin.py, combined log text).
    """
    with tempfile.TemporaryDirectory() as out:
        cmd = ["docker", "run", "--rm", "--network", "none",
               "-v", f"{PLUGIN_DIR}:/factory:ro", "-v", f"{out}:/out",
               "-e", "PYTHONPATH=/factory", "-e", "FACTORY_REPORT=/out/report.jsonl"]
        if workdir is not None:
            cmd += ["-v", f"{Path(workdir).resolve()}:/work/click"]
        cmd += [adapter_click.image(pin), "python", "-m", "pytest", "-p", "report_plugin",
                "-p", "no:cacheprovider", "-q", *args]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        report = Path(out) / "report.jsonl"
        rows = [json.loads(l) for l in report.read_text().splitlines()] if report.exists() else []
    return rows, proc.stdout + proc.stderr


_MISSING_API = {"AttributeError", "ImportError", "ModuleNotFoundError", "NoSuchOption"}


def _classify(longrepr: str) -> str:
    """Kind of a test failure, from the crash line pytest prints last (`path:line: ExcType`)."""
    last = longrepr.strip().splitlines()[-1] if longrepr.strip() else ""
    m = re.search(r":\d+: (\w+)$", last)
    exc = m.group(1) if m else ""
    if exc in _MISSING_API or (exc == "TypeError" and "unexpected keyword argument" in longrepr):
        return "missing_api"
    if exc == "AssertionError":
        return "assertion"
    return "error"


def _checkout(pin: RepoPin, dest: Path) -> None:
    archive = subprocess.run(["git", "-C", str(adapter_click.repo_dir(pin)), "archive", pin.sha],
                             capture_output=True, check=True)
    dest.mkdir(parents=True)
    subprocess.run(["tar", "-x", "-C", str(dest)], input=archive.stdout, check=True)


def apply_check(pin: RepoPin, patch: str) -> tuple[bool, str]:
    """Does `patch` apply cleanly to the pinned commit? Runs on the host; nothing is executed."""
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "click"
        _checkout(pin, work)
        proc = subprocess.run(["git", "apply", "--check", str(Path(patch).resolve())],
                              cwd=work, capture_output=True, text=True)
    return proc.returncode == 0, proc.stderr.strip()


def _log(pair_id: str | None, text: str) -> str:
    logs = adapter_click._runs() / (pair_id or "adhoc") / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.log"
    path.write_text(text)
    return str(path)


def run_tests(pin: RepoPin, patches: list[str], test_files: list[str] | None = None, repeat: int = 1,
              pair_id: str | None = None) -> TestRun:
    """Apply `patches` to a clean pinned checkout and run pytest in Docker.

    test_files=None runs click's existing suite (FLAKY / ENV_EXCLUDED ignored);
    otherwise the files are copied to _feature_tests/ and only they run.
    With repeat > 1 a test counts as passed only if it passed every time.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "click"
        _checkout(pin, work)
        log = []
        for patch in patches:
            proc = subprocess.run(["git", "apply", str(Path(patch).resolve())], cwd=work, capture_output=True, text=True)
            if proc.returncode != 0:
                text = f"git apply failed for {patch}:\n{proc.stderr}"
                targets = [f"_feature_tests/{Path(f).name}" for f in test_files] if test_files else [adapter_click.EXISTING_TESTS]
                return TestRun(passed=[], failed={t: "error" for t in targets}, log_path=_log(pair_id, text))
        if test_files:
            (work / "_feature_tests").mkdir()
            for f in test_files:
                shutil.copy(f, work / "_feature_tests" / Path(f).name)
            args = [f"_feature_tests/{Path(f).name}" for f in test_files]
        else:
            args = [adapter_click.EXISTING_TESTS]

        passed_every: set[str] | None = None
        failed: dict[str, str] = {}
        for _ in range(repeat):
            rows, text = _run_pytest(pin, work, args)
            log.append(text)
            passed = {r["nodeid"] for r in rows if r["when"] == "call" and r["outcome"] == "passed"}
            for r in rows:
                if r["outcome"] == "failed" and r["nodeid"] not in failed:
                    failed[r["nodeid"]] = "collection" if r["when"] == "collect" else (
                        _classify(r["longrepr"]) if r["when"] == "call" else "error")
            passed_every = passed if passed_every is None else passed_every & passed
        flipped = {t for t in failed if t in passed_every}
        passed_every -= flipped
        keep = (lambda t: not adapter_click.is_excluded(t)) if not test_files else (lambda t: True)
        return TestRun(passed=sorted(t for t in passed_every if keep(t)),
                       failed={t: k for t, k in sorted(failed.items()) if keep(t)},
                       log_path=_log(pair_id, "\n".join(log)))

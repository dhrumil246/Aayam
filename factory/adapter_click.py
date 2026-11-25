"""Everything specific to pallets/click. Owner: Dhrumil.

A second target repo means writing a second adapter file like this one.
"""
from __future__ import annotations

import fnmatch
import json
import shutil
import subprocess
from pathlib import Path

from factory.schema import RepoPin

ROOT = Path(__file__).resolve().parent.parent
_PIN = json.loads((ROOT / "factory" / "pin.json").read_text())
PIN = RepoPin(repo=_PIN["repo"], tag=_PIN["tag"], sha=_PIN["sha"])
BASE_IMAGE: str = _PIN["base_image"]
EXISTING_TESTS = "tests/"
# Tests that fail on the unpatched pin only because the slim image lacks a system
# tool. Excluded identically in every run (G0, G2, sandbox), like FLAKY.
ENV_EXCLUDED: dict[str, str] = {
    "tests/test_utils/test_echo_via_pager.py::test_echo_via_pager[[]*less*[]]": "no `less` binary in python:3.12-slim",
}
_FLAKY_FILE = ROOT / "factory" / "flaky.json"
FLAKY: list[str] = json.loads(_FLAKY_FILE.read_text()) if _FLAKY_FILE.exists() else []


def _runs() -> Path:
    import os
    return Path(os.environ.get("FACTORY_RUNS", "runs"))


def repo_dir(pin: RepoPin) -> Path:
    """Clean checkout of the pinned commit, cached at runs/repos/<sha>/."""
    dest = _runs() / "repos" / pin.sha
    if not (dest / ".git").exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", f"https://github.com/{pin.repo}", str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "-q", "--detach", pin.sha], check=True)
    return dest


def image(pin: RepoPin) -> str:
    """Build the pinned image once; tag factory-click:<sha[:12]>."""
    tag = f"factory-click:{pin.sha[:12]}"
    if subprocess.run(["docker", "image", "inspect", tag], capture_output=True).returncode == 0:
        return tag
    ctx = _runs() / "build" / pin.sha
    shutil.rmtree(ctx, ignore_errors=True)
    (ctx / "click").mkdir(parents=True)
    archive = subprocess.run(["git", "-C", str(repo_dir(pin)), "archive", pin.sha], capture_output=True, check=True)
    subprocess.run(["tar", "-x", "-C", str(ctx / "click")], input=archive.stdout, check=True)
    shutil.copy(ROOT / "docker" / "requirements.lock", ctx / "requirements.lock")
    subprocess.run(["docker", "build", "-q", "-t", tag, "-f", str(ROOT / "docker" / "click.Dockerfile"), str(ctx)],
                   check=True, capture_output=True)
    return tag


def is_excluded(nodeid: str) -> bool:
    return nodeid in FLAKY or any(fnmatch.fnmatchcase(nodeid, p) for p in ENV_EXCLUDED)


def save_flaky(tests: list[str]) -> None:
    _FLAKY_FILE.write_text(json.dumps(sorted(tests), indent=2) + "\n")
    FLAKY[:] = sorted(tests)

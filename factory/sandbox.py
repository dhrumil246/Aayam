"""Run pytest against a (patched) click checkout inside Docker. Owner: Dhrumil."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from factory import adapter_click
from factory.schema import RepoPin

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

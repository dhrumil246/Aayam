"""Run one click invocation against a patched click inside Docker. Owner: Dhrumil."""
from __future__ import annotations

import json
import select
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path

from factory import adapter_click, sandbox
from factory.schema import Invocation, Outcome, RepoPin


class Worker:
    """A persistent container for one (pin, patch, demo_app). Use as a context manager."""

    def __init__(self, pin: RepoPin, patch: str | None, demo_app: str):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self._work = root / "click"
        sandbox._checkout(pin, self._work)
        if patch:
            proc = subprocess.run(["git", "apply", str(Path(patch).resolve())], cwd=self._work,
                                  capture_output=True, text=True)
            if proc.returncode != 0:
                self._tmp.cleanup()
                raise ValueError(f"patch does not apply: {proc.stderr.strip()}")
        (root / "demo").mkdir()
        (root / "demo" / "app.py").write_text(demo_app)
        self._cmd = ["docker", "run", "-i", "--rm", "--network", "none",
                     "-v", f"{self._work}:/work/click", "-v", f"{root / 'demo'}:/demo:ro",
                     "-v", f"{sandbox.PLUGIN_DIR}:/factory:ro",
                     adapter_click.image(pin), "python", "-u", "/factory/harness.py"]
        self._proc: subprocess.Popen | None = None

    STARTUP_GRACE = 5.0  # seconds; container start-up is not the demo app's fault

    def _start(self) -> tuple[subprocess.Popen, bool]:
        if self._proc is None or self._proc.poll() is not None:
            self._proc = subprocess.Popen(self._cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL, text=True, bufsize=1)
            return self._proc, True
        return self._proc, False

    def call(self, inv: Invocation, timeout: float = 10.0) -> Outcome:
        proc, started = self._start()
        proc.stdin.write(json.dumps(asdict(inv)) + "\n")
        proc.stdin.flush()
        ready, _, _ = select.select([proc.stdout], [], [], timeout + (self.STARTUP_GRACE if started else 0))
        line = proc.stdout.readline() if ready else ""
        if not line:
            self._kill()
            return Outcome(-1, "", "Timeout")
        return Outcome(**json.loads(line))

    def _kill(self) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc.wait()
            self._proc = None

    def close(self) -> None:
        self._kill()
        self._tmp.cleanup()

    def __enter__(self) -> "Worker":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def fresh_call(pin: RepoPin, patch: str | None, demo_app: str, inv: Invocation) -> Outcome:
    """One invocation in a brand-new container (used to confirm findings)."""
    with Worker(pin, patch, demo_app) as w:
        return w.call(inv)

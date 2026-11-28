"""Reference patch generation and repair against the pinned click repo. Owner: Akshat."""
from __future__ import annotations

import re
from pathlib import Path

from factory import adapter_click, sandbox, worker
from factory.llm import llm, llm_json, load_prompt
from factory.schema import Contract, Patch, RepoPin

MAX_ITERATIONS = 3


def _extract_diff(text: str) -> str:
    m = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, re.S)
    diff = m.group(1) if m else text
    return diff.strip() + "\n"


def _touched_paths(diff: str) -> list[str]:
    paths: list[str] = []
    for line in diff.splitlines():
        if line.startswith(("+++ b/", "--- a/")):
            p = line[6:].strip()
            if p != "/dev/null":
                paths.append(p)
    return paths


def _select_files(repo: Path, ticket: str, pair_id: str) -> dict[str, str]:
    src_files = sorted(p.relative_to(repo).as_posix() for p in (repo / "src" / "click").rglob("*.py"))
    prompt = load_prompt("propose", "reference_files", available_files="\n".join(src_files), ticket=ticket)
    resp = llm_json(prompt, role="reference_files", pair_id=pair_id)
    chosen = [str(f) for f in resp.get("files", []) if str(f) in src_files][:6] or ["src/click/core.py"]
    return {rel: (repo / rel).read_text(encoding="utf-8") for rel in chosen}


def _format_files(files: dict[str, str]) -> str:
    return "\n\n".join(f"### {path}\n```python\n{body}\n```" for path, body in files.items())


def _verify_diff(diff: str, contract: Contract, pin: RepoPin, out: Path) -> str | None:
    paths = _touched_paths(diff)
    if not paths:
        return "Diff touched no files."
    bad_paths = [p for p in paths if p.startswith("tests/") or not p.startswith("src/")]
    if bad_paths:
        return f"Reference patches must only modify src/ files, not: {bad_paths}"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(diff, encoding="utf-8", newline="\n")

    ok, err = sandbox.apply_check(pin, str(out))
    if not ok:
        return f"Patch failed to apply: {err}"

    tr = sandbox.run_tests(pin, [str(out)], pair_id=contract.pair_id)
    if tr.failed:
        sample = list(tr.failed.items())[:10]
        return f"Existing click tests failed ({len(tr.failed)}): {sample}"

    outcome = worker.fresh_call(pin, str(out), contract.demo_app, contract.probe)
    if outcome.exception_type not in (None, "SystemExit"):
        return f"Probe raised unexpected exception {outcome.exception_type}: {outcome.output}"

    return None


def write_reference(contract: Contract, ticket: str, pin: RepoPin, out: Path) -> Patch:
    """Write a reference unified diff for one side, verified in the sandbox."""
    repo = adapter_click.repo_dir(pin)
    files = _select_files(repo, ticket, contract.pair_id)
    files_content = _format_files(files)
    feedback = ""
    last_err = ""
    for _ in range(MAX_ITERATIONS):
        prompt = load_prompt(
            "propose",
            "reference",
            ticket=ticket,
            public_api=contract.public_api,
            files_content=files_content,
            feedback=feedback,
        )
        diff = _extract_diff(llm(prompt, role="reference", pair_id=contract.pair_id))
        err = _verify_diff(diff, contract, pin, out)
        if err is None:
            return Patch(path=str(out), kind="reference", side=contract.side)
        last_err = err
        feedback = f"Previous attempt failed:\n{err}"
    raise ValueError(f"write_reference failed after {MAX_ITERATIONS} attempts: {last_err}")


def repair_reference(contract: Contract, ticket: str, pin: RepoPin, patch: Patch, failure: str) -> Patch:
    """Repair a reference patch given a sandbox or shared-clause failure."""
    repo = adapter_click.repo_dir(pin)
    files = _select_files(repo, ticket, contract.pair_id)
    files_content = _format_files(files)
    out = Path(patch.path)
    prev_diff = out.read_text(encoding="utf-8") if out.exists() else ""
    cur_failure = failure
    for _ in range(MAX_ITERATIONS):
        prompt = load_prompt(
            "propose",
            "repair_reference",
            ticket=ticket,
            prev_diff=prev_diff,
            failure=cur_failure,
            files_content=files_content,
        )
        diff = _extract_diff(llm(prompt, role="repair_reference", pair_id=contract.pair_id))
        err = _verify_diff(diff, contract, pin, out)
        if err is None:
            return Patch(path=str(out), kind="reference", side=contract.side)
        prev_diff = diff
        cur_failure = err
    raise ValueError(f"repair_reference failed after {MAX_ITERATIONS} attempts: {cur_failure}")

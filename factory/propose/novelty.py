"""Gate G8: novelty check against click main, docs, CHANGES, and issues/PRs. Owner: Akshat."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from factory import adapter_click
from factory.llm import llm_json, load_prompt
from factory.schema import GateResult, Seed

_SEARCH_PATHS = ("src", "docs", "CHANGES.rst")
_ONE_DAY_SECS = 86400


def _ensure_main_repo() -> Path:
    dest = adapter_click._runs() / "repos" / "main"
    offline = os.environ.get("FACTORY_OFFLINE") == "1"
    if not (dest / ".git").exists():
        if offline:
            return adapter_click.repo_dir(adapter_click.PIN)
        dest.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "-q", "--branch", "main", "--single-branch", f"https://github.com/{adapter_click.PIN.repo}", str(dest)],
            check=True,
        )
        return dest
    if not offline and time.time() - dest.stat().st_mtime > _ONE_DAY_SECS:
        subprocess.run(["git", "-C", str(dest), "pull", "-q", "--ff-only"], check=False)
    return dest


def _grep_repo(repo: Path, terms: list[str], limit_per_term: int = 8) -> list[str]:
    matches: list[str] = []
    targets = [repo / p for p in _SEARCH_PATHS if (repo / p).exists()]
    if not targets:
        return matches
    files: list[Path] = []
    for t in targets:
        if t.is_file():
            files.append(t)
        else:
            files.extend(p for p in t.rglob("*") if p.is_file() and p.suffix in {".py", ".rst", ".md", ".txt", ""})
    for term in terms:
        needle = term.lower()
        found_for_term = 0
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), 1):
                if needle in line.lower():
                    rel = f.relative_to(repo).as_posix()
                    matches.append(f"{rel}:{idx}: {line.strip()[:120]}")
                    found_for_term += 1
                    if found_for_term >= limit_per_term:
                        break
            if found_for_term >= limit_per_term:
                break
    return matches


def _gh_titles(terms: list[str]) -> list[str]:
    cache_path = adapter_click._runs() / "gh_titles.json"
    cached: dict[str, list[str]] = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
    offline = os.environ.get("FACTORY_OFFLINE") == "1"
    gh_bin = shutil.which("gh")
    results: list[str] = []
    updated = False
    for term in terms:
        if term in cached:
            results.extend(cached[term])
            continue
        if offline or not gh_bin:
            continue
        term_hits: list[str] = []
        for kind in ("issues", "prs"):
            proc = subprocess.run(
                [gh_bin, "search", kind, "--repo", adapter_click.PIN.repo, term, "--limit", "5", "--json", "title"],
                capture_output=True,
                text=True,
                check=False,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    for item in json.loads(proc.stdout):
                        term_hits.append(f"gh:{kind}: {item.get('title', '')}")
                except json.JSONDecodeError:
                    pass
        cached[term] = term_hits
        results.extend(term_hits)
        updated = True
    if updated:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(cached, indent=2), encoding="utf-8")
    return results


def novelty_gate(seed: Seed) -> GateResult:
    """Return GateResult(gate='G8', ...) checking that seed is not already in click."""
    terms_prompt = load_prompt("propose", "novelty_terms", feature=seed.feature)
    terms_data = llm_json(terms_prompt, role="novelty_terms", pair_id=seed.pair_id)
    terms = [str(t).strip() for t in terms_data.get("terms", []) if str(t).strip()][:5]

    repo = _ensure_main_repo()
    matches = _grep_repo(repo, terms) + _gh_titles(terms)

    judge_prompt = load_prompt(
        "propose",
        "novelty_judge",
        feature=seed.feature,
        terms=", ".join(terms),
        matches="\n".join(matches) if matches else "(no matches)",
    )
    verdict = llm_json(judge_prompt, role="novelty_judge", pair_id=seed.pair_id)
    already_exists = bool(verdict.get("already_exists", False))
    return GateResult(
        gate="G8",
        passed=not already_exists,
        detail={"terms": terms, "matches": matches, "reason": str(verdict.get("reason", ""))},
    )

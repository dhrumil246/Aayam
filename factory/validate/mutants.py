"""G6: requirement-targeted mutants and the kill check.

Owner: Urja. A mutant is a complete, plausible implementation (a diff
against the pinned base) that breaks exactly one requirement. Only a grader
test failing with an assertion or a missing API counts as a kill; a mutant
that doesn't apply or crashes everything is "invalid", not killed.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from factory import sandbox
from factory.llm import DEFAULT_MODEL, llm, load_prompt
from factory.schema import Contract, GateResult, Pair, Patch

MAX_TRIES = 3  # first try + 2 retries
KILL_KINDS = ("assertion", "missing_api")


def _extract_diff(text: str) -> str | None:
    blocks = re.findall(r"```(?:diff|patch)?[ \t]*\n(.*?)```", text, re.S)
    for candidate in [*blocks, text]:
        candidate = candidate.strip("\n")
        if re.search(r"^--- ", candidate, re.M) and re.search(r"^\+\+\+ ", candidate, re.M) \
                and re.search(r"^@@ ", candidate, re.M):
            start = re.search(r"^(diff --git |--- )", candidate, re.M).start()
            return candidate[start:] + "\n"
    return None


def make_mutants(contract: Contract, ticket: str, reference: Patch, out_dir: Path) -> list[Patch]:
    """Write one plausible wrong patch per requirement into `out_dir`.

    A requirement whose mutant still isn't a usable diff after the retries is
    skipped; G7 then reports that requirement as having no killed mutant.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ref_text = Path(reference.path).read_text()
    model = os.environ.get("FACTORY_MODEL_DEFAULT", DEFAULT_MODEL)
    others = {r.id: r.text for r in contract.requirements}
    patches = []
    for req in contract.requirements:
        prompt = load_prompt(
            "validate", "mutant",
            ticket=ticket, reference=ref_text, public_api=contract.public_api,
            requirement_id=req.id, requirement=req.text,
            others="\n".join(f"- {k}: {v}" for k, v in others.items() if k != req.id) or "- (none)",
        )
        for attempt in range(1, MAX_TRIES + 1):
            ask = prompt if attempt == 1 else (
                f"{prompt}\n\nAttempt {attempt} of {MAX_TRIES}. Your previous reply had no unified diff "
                "(--- / +++ / @@ lines). Reply with the diff in one ```diff block.")
            diff = _extract_diff(llm(ask, role="mutant", model=model))
            if diff:
                path = out_dir / f"mutant_{contract.side}_{req.id}.patch"
                path.write_text(diff)
                patches.append(Patch(str(path), "mutant", side=contract.side, requirement_id=req.id, model=model))
                break
    return patches


def g6_mutants(pair: Pair, side: str, mutants: list[Patch]) -> GateResult:
    """Run the grader on each mutant (gate="G6", detail["killed"], detail["survivors"]).

    Passes when at least one mutant is killed and none survive. Whether every
    requirement has a killed mutant is G7's job.
    """
    grader = pair.graders[side]
    killed: dict[str, list[str]] = {}
    survivors: list[str] = []
    invalid: list[str] = []
    logs: dict[str, str] = {}
    for m in mutants:
        run = sandbox.run_tests(pair.pin, [m.path], [grader], pair_id=pair.seed.pair_id)
        logs[m.path] = run.log_path
        kills = sorted(t for t, kind in run.failed.items() if kind in KILL_KINDS and "::" in t)
        if kills:
            killed[m.path] = kills
        elif run.failed:
            invalid.append(m.path)  # didn't apply, crashed, or failed only with errors: graded nothing
        else:
            survivors.append(m.path)
    detail = {
        "killed": killed,
        "survivors": survivors,
        "invalid": invalid,
        "mutant_requirements": {m.path: m.requirement_id for m in mutants},
        "logs": logs,
    }
    return GateResult("G6", passed=bool(killed) and not survivors, detail=detail)

"""Differential search between two patched copies of click.

Owner: Urja. A lead finder, not an oracle: findings become tests only after
expectations are derived from the tickets. Hypothesis shrinking gives a
small example, not a guaranteed shortest one. Also used by Heet (solver vs
reference), so `patch_b` can be any patch.
"""
from __future__ import annotations

import json

from hypothesis import HealthCheck, find, settings
from hypothesis import strategies as st
from hypothesis.errors import NoSuchExample

from factory.llm import llm_json, load_prompt
from factory.schema import Finding, FindingLabel, Invocation, Outcome, RepoPin
from factory.worker import Worker, fresh_call

DEFAULT_MAX_TOKENS = 6
LABELS = ("pivot", "shared", "open")
MAX_TRIES = 3  # first try + 2 retries


# ---- input generation -------------------------------------------------------

def invocations(grammar: dict) -> st.SearchStrategy[Invocation]:
    """Hypothesis strategy drawing invocations from a contract grammar (format in AGENTS.md).

    argv is a list of option/arg groups in any order: a flag is one token, a
    value option is `[flag, value]` (kept together), a positional arg is one
    value. The whole argv is at most `max_tokens` strings, and each arg
    appears at most its `max` times. env is any subset of the grammar's
    variables; stdin is one of the grammar's choices (None if it has none).
    """
    max_tokens = grammar.get("max_tokens", DEFAULT_MAX_TOKENS)
    groups: list[tuple[str | None, tuple[str, ...]]] = []  # (arg name or None, tokens)
    for opt in grammar["options"]:
        if opt.get("kind") == "value":
            groups += [(None, (opt["flag"], v)) for v in opt.get("values", [])]
        else:
            groups.append((None, (opt["flag"],)))
    arg_max = {}
    for arg in grammar.get("args", []):
        arg_max[arg["name"]] = arg.get("max", max_tokens)
        groups += [(arg["name"], (v,)) for v in arg["values"]]

    def to_argv(chosen: list[tuple[str | None, tuple[str, ...]]]) -> list[str]:
        argv: list[str] = []
        used: dict[str, int] = {}
        for name, tokens in chosen:
            if name is not None:
                if used.get(name, 0) >= arg_max[name]:
                    continue
                used[name] = used.get(name, 0) + 1
            if len(argv) + len(tokens) > max_tokens:
                continue
            argv += tokens
        return argv

    argv = st.lists(st.sampled_from(groups), max_size=max_tokens).map(to_argv) if groups else st.just([])
    env = st.fixed_dictionaries({}, optional={k: st.sampled_from(v) for k, v in grammar.get("env", {}).items() if v})
    stdin = st.sampled_from(grammar["stdin"]) if grammar.get("stdin") else st.none()
    return st.builds(Invocation, argv=argv, env=env, input=stdin)


# ---- comparison -------------------------------------------------------------

def _norm(output: str) -> str:
    return "\n".join(line.rstrip() for line in output.splitlines()).rstrip("\n")


def same_outcome(a: Outcome, b: Outcome) -> bool:
    """Equal up to trailing whitespace on each line and trailing blank lines."""
    return (a.exit_code == b.exit_code and a.exception_type == b.exception_type
            and _norm(a.output) == _norm(b.output))


# ---- search -----------------------------------------------------------------

def diff_search(pin: RepoPin, patch_a: str | None, patch_b: str | None, demo_app: str,
                grammar: dict, budget: int = 200) -> list[Finding]:
    """Find, shrink and fresh-replay an input where the two patches disagree.

    Returns at most one finding. Returns [] when no disagreement is found
    within `budget` examples ("no distinguishing case found within budget";
    that doesn't prove there is none) or when the case found doesn't
    reproduce in fresh processes.
    """
    with Worker(pin, patch_a, demo_app) as wa, Worker(pin, patch_b, demo_app) as wb:
        def disagrees(inv: Invocation) -> bool:
            return not same_outcome(wa.call(inv), wb.call(inv))

        try:
            inv = find(invocations(grammar), disagrees,
                       settings=settings(max_examples=budget, database=None, deadline=None,
                                         suppress_health_check=list(HealthCheck)))
        except NoSuchExample:
            return []

    # Persistent workers could leak state between calls; only a case that
    # still disagrees in brand-new processes counts.
    out_a = fresh_call(pin, patch_a, demo_app, inv)
    out_b = fresh_call(pin, patch_b, demo_app, inv)
    if same_outcome(out_a, out_b):
        return []
    return [Finding(inv, out_a, out_b, replayed_fresh=True)]


# ---- classification ---------------------------------------------------------

def _outcome_text(o: Outcome) -> str:
    return json.dumps({"exit_code": o.exit_code, "output": o.output, "exception_type": o.exception_type},
                      indent=2)


def classify_finding(finding: Finding, ticket_a: str, ticket_b: str) -> FindingLabel:
    """Label a finding as "pivot", "shared" or "open" against the two tickets."""
    inv = finding.invocation
    prompt = load_prompt(
        "validate", "classify",
        ticket_a=ticket_a, ticket_b=ticket_b,
        argv=json.dumps(inv.argv), env=json.dumps(inv.env, sort_keys=True), stdin=json.dumps(inv.input),
        outcome_a=_outcome_text(finding.outcome_a), outcome_b=_outcome_text(finding.outcome_b),
    )
    ask, bad = prompt, None
    for attempt in range(1, MAX_TRIES + 1):
        reply = llm_json(ask, role="classify")
        label = reply.get("label") if isinstance(reply, dict) else None
        if label in LABELS:
            return label
        bad = label
        ask = (f"{prompt}\n\nAttempt {attempt + 1} of {MAX_TRIES}. Your previous label {label!r} "
               f"is not one of {list(LABELS)}. Reply with JSON only.")
    raise ValueError(f"no valid label after {MAX_TRIES} tries (last: {bad!r})")

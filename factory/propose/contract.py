"""Frozen twin contracts and deterministic contract validation. Owner: Akshat."""
from __future__ import annotations

import ast
import re

from factory.llm import llm_json, load_prompt
from factory.schema import Contract, Invocation, Requirement, Seed, _build

_WORDING_STOPWORDS = frozenset(
    {
        "cannot",
        "can't",
        "conflicts",
        "conflict",
        "mutually",
        "exclusive",
        "invalid",
        "illegal",
        "error",
        "usage",
        "combine",
        "combined",
        "together",
        "message",
        "says",
        "with",
    }
)


def _has_top_level_cli(source: str) -> bool:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "cli":
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "cli":
                    return True
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "cli":
            return True
    return False


def _allowed_tokens(grammar: dict) -> tuple[set[str], set[str], set[str]]:
    flags: set[str] = set()
    opt_values: set[str] = set()
    arg_values: set[str] = set()
    for opt in grammar.get("options", []):
        if isinstance(opt, dict) and "flag" in opt:
            flags.add(str(opt["flag"]))
            for val in opt.get("values", []):
                opt_values.add(str(val))
    for arg in grammar.get("args", []):
        if isinstance(arg, dict):
            for val in arg.get("values", []):
                arg_values.add(str(val))
    return flags, opt_values, arg_values


def _probe_in_grammar(probe: Invocation, grammar: dict) -> list[str]:
    errors: list[str] = []
    options = grammar.get("options")
    if not isinstance(options, list) or not options:
        return ["grammar.options must be a non-empty list"]
    max_tokens = grammar.get("max_tokens")
    if isinstance(max_tokens, int) and len(probe.argv) > max_tokens:
        errors.append(f"probe.argv length {len(probe.argv)} exceeds grammar.max_tokens ({max_tokens})")
    flags, opt_values, arg_values = _allowed_tokens(grammar)
    all_tokens = flags | opt_values | arg_values
    for tok in probe.argv:
        if tok in all_tokens:
            continue
        if "=" in tok:
            flag_part, val_part = tok.split("=", 1)
            if flag_part in flags and val_part in opt_values:
                continue
        errors.append(f"probe token {tok!r} is not drawable from grammar")
    env_spec = grammar.get("env", {})
    for k, v in probe.env.items():
        if k not in env_spec or v not in env_spec[k]:
            errors.append(f"probe env {k}={v!r} is not in grammar.env")
    if probe.input is not None:
        stdin_spec = grammar.get("stdin", [])
        if probe.input not in stdin_spec:
            errors.append(f"probe input {probe.input!r} is not in grammar.stdin")
    return errors


def _normalize_for_wording_check(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9_]+", text.lower())
    return [w for w in words if w not in _WORDING_STOPWORDS]


def validate_contracts(a: Contract, b: Contract) -> list[str]:
    """Return validation error messages for twin contracts A and B (empty means valid)."""
    errors: list[str] = []
    if a.side != "A":
        errors.append(f"contract A has side={a.side!r}, expected 'A'")
    if b.side != "B":
        errors.append(f"contract B has side={b.side!r}, expected 'B'")
    if a.pair_id != b.pair_id:
        errors.append(f"pair_id mismatch: {a.pair_id!r} vs {b.pair_id!r}")
    if a.family != b.family:
        errors.append(f"family mismatch: {a.family!r} vs {b.family!r}")

    a_pivots = [r for r in a.requirements if r.pivot]
    b_pivots = [r for r in b.requirements if r.pivot]
    if len(a_pivots) != 1:
        errors.append(f"contract A must have exactly 1 pivot requirement, found {len(a_pivots)}")
    if len(b_pivots) != 1:
        errors.append(f"contract B must have exactly 1 pivot requirement, found {len(b_pivots)}")

    a_shared = [(r.id, r.text) for r in a.requirements if not r.pivot]
    b_shared = [(r.id, r.text) for r in b.requirements if not r.pivot]
    if a_shared != b_shared:
        errors.append("shared requirements must be text-identical between A and B")

    if len(a_pivots) == 1 and len(b_pivots) == 1:
        pa, pb = a_pivots[0], b_pivots[0]
        if pa.id != pb.id:
            errors.append(f"pivot requirement id mismatch: {pa.id!r} vs {pb.id!r}")
        if pa.text.strip() == pb.text.strip():
            errors.append("pivot requirement text must differ between A and B")
        elif _normalize_for_wording_check(pa.text) == _normalize_for_wording_check(pb.text):
            errors.append("pivot difference appears to be error wording only, not a behavioural rule")

    if a.demo_app != b.demo_app:
        errors.append("demo_app must be identical for A and B")
    try:
        compile(a.demo_app, "<demo_app>", "exec")
        if not _has_top_level_cli(a.demo_app):
            errors.append("demo_app must define a top-level `cli` command or group")
    except SyntaxError as exc:
        errors.append(f"demo_app has syntax error: {exc}")

    if a.grammar != b.grammar:
        errors.append("grammar must be identical for A and B")
    if a.probe != b.probe:
        errors.append("probe must be identical for A and B")
    errors.extend(_probe_in_grammar(a.probe, a.grammar))
    return errors


def write_contracts(seed: Seed, surface: str) -> tuple[Contract, Contract]:
    """Generate and validate frozen twin contracts A and B from a seed."""
    feedback = ""
    last_errors: list[str] = []
    for _attempt in range(3):
        prompt = load_prompt(
            "propose",
            "contract",
            pair_id=seed.pair_id,
            family=seed.family,
            feature=seed.feature,
            policy_a=seed.policy_a,
            policy_b=seed.policy_b,
            surface=surface,
            feedback=feedback,
        )
        raw = llm_json(prompt, role="contracts", pair_id=seed.pair_id)
        a = _build(Contract, raw["A"])
        b = _build(Contract, raw["B"])
        last_errors = validate_contracts(a, b)
        if not last_errors:
            return a, b
        feedback = "Previous attempt failed validation with:\n" + "\n".join(f"- {e}" for e in last_errors)
    raise ValueError("invalid contracts after retries: " + "; ".join(last_errors))

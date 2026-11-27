"""Ticket-derived expectations for a probe.

Owner: Urja. Expected outcomes come from one ticket only, never from a
reference's output. Imported by Heet's code, so keep it free of any
reference-patch knowledge.
"""
from __future__ import annotations

import ast
import json

from factory.llm import llm_json, load_prompt
from factory.schema import Assertion, Invocation, Outcome

OUTCOME_FIELDS = {"exit_code", "output", "exception_type"}
STR_METHODS = {"lower", "count", "find", "strip", "splitlines"}
COMPARE_OPS = (ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn)
MAX_TRIES = 3  # first try + 2 retries


def derive_expectations(ticket: str, probe: Invocation, requirement_id: str) -> list[Assertion]:
    """Ask a model, shown only `ticket` and `probe`, what the ticket determines about the outcome."""
    prompt = load_prompt(
        "validate", "expect",
        ticket=ticket,
        requirement_id=requirement_id,
        argv=json.dumps(probe.argv),
        env=json.dumps(probe.env, sort_keys=True),
        stdin=json.dumps(probe.input),
    )
    errors: list[str] = []
    for attempt in range(1, MAX_TRIES + 1):
        ask = prompt if not errors else (
            f"{prompt}\n\nAttempt {attempt} of {MAX_TRIES}. Your previous answer was rejected:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix these and reply with the full JSON list again."
        )
        reply = llm_json(ask, role="expect")
        assertions, errors = _parse_reply(reply, requirement_id)
        if not errors:
            return assertions
    raise ValueError(f"no valid expectations for {requirement_id} after {MAX_TRIES} tries: {errors}")


def _parse_reply(reply, requirement_id: str) -> tuple[list[Assertion], list[str]]:
    if isinstance(reply, dict) and isinstance(reply.get("assertions"), list):
        reply = reply["assertions"]
    if not isinstance(reply, list):
        return [], ["reply must be a JSON list of {\"description\", \"python\"} objects"]
    assertions, errors = [], []
    for i, item in enumerate(reply):
        if not (isinstance(item, dict) and isinstance(item.get("python"), str)):
            errors.append(f"item {i} needs a string \"python\" field")
            continue
        a = Assertion(requirement_id, str(item.get("description", "")), item["python"].strip())
        errors += [f"{a.python!r}: {e}" for e in validate_assertion(a)]
        assertions.append(a)
    return assertions, errors


def validate_assertion(a: Assertion) -> list[str]:
    """Return problems with `a.python` (empty list = safe to evaluate)."""
    try:
        tree = ast.parse(a.python, mode="eval")
    except SyntaxError as e:
        return [f"not a single Python expression: {e.msg}"]
    errors: list[str] = []
    body = tree.body
    if not isinstance(body, (ast.Compare, ast.BoolOp, ast.UnaryOp)):
        errors.append("must be a boolean check (a comparison, and/or, or not)")
    _check_node(body, errors)
    if not any(isinstance(n, ast.Name) and n.id == "outcome" for n in ast.walk(tree)):
        errors.append("never looks at `outcome`, so it can't tell outcomes apart")
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(ast.dump(x) == ast.dump(y) for x, y in zip(sides, sides[1:])):
                errors.append("compares an expression with itself")
    return errors


def _check_node(node: ast.AST, errors: list[str]) -> None:
    match node:
        case ast.BoolOp(op=ast.And() | ast.Or(), values=values):
            for v in values:
                _check_node(v, errors)
        case ast.UnaryOp(op=ast.Not(), operand=operand):
            _check_node(operand, errors)
        case ast.Compare(left=left, ops=ops, comparators=comparators):
            sides = [left, *comparators]
            for op, x, y in zip(ops, sides, sides[1:]):
                if isinstance(op, (ast.Is, ast.IsNot)):
                    if not any(isinstance(s, ast.Constant) and s.value is None for s in (x, y)):
                        errors.append("`is` / `is not` only against None")
                elif not isinstance(op, COMPARE_OPS):
                    errors.append(f"operator {type(op).__name__} not allowed")
            for s in sides:
                _check_node(s, errors)
        case ast.Constant(value=value):
            if not isinstance(value, (str, int, float, bool, type(None))):
                errors.append(f"literal {value!r} not allowed")
        case ast.Tuple(elts=elts) | ast.List(elts=elts):
            for e in elts:
                _check_node(e, errors)
        case ast.Attribute(value=ast.Name(id="outcome"), attr=attr):
            if attr not in OUTCOME_FIELDS:
                errors.append(f"outcome.{attr} not allowed (use {sorted(OUTCOME_FIELDS)})")
        case ast.Name(id="outcome"):
            pass
        case ast.Call(func=func, args=args, keywords=keywords):
            if keywords:
                errors.append("keyword arguments not allowed")
            match func:
                case ast.Name(id="len"):
                    if len(args) != 1:
                        errors.append("len() takes one argument")
                case ast.Attribute(value=target, attr=attr) if attr in STR_METHODS:
                    _check_node(target, errors)
                case ast.Name(id=name) | ast.Attribute(attr=name):
                    errors.append(f"call to {name} not allowed (only len() and {sorted(STR_METHODS)})")
                case _:
                    errors.append("call not allowed")
            for arg in args:
                _check_node(arg, errors)
        case ast.Name(id=name):
            errors.append(f"name {name} not allowed (only `outcome`)")
        case _:
            errors.append(f"{type(node).__name__} not allowed")


def check(assertions: list[Assertion], outcome: Outcome) -> list[tuple[Assertion, bool]]:
    """Evaluate each validated assertion against `outcome`.

    Raises ValueError if any assertion fails validation. An assertion that
    raises while evaluating (e.g. `.lower()` on a None exception_type) counts
    as not satisfied.
    """
    for a in assertions:
        if errors := validate_assertion(a):
            raise ValueError(f"invalid assertion {a.python!r}: {errors}")
    results = []
    for a in assertions:
        code = compile(a.python, "<assertion>", "eval")
        try:
            ok = bool(eval(code, {"__builtins__": {"len": len}}, {"outcome": outcome}))
        except Exception:
            ok = False
        results.append((a, ok))
    return results

"""Hidden grader generation, naming checks and repair.

Owner: Urja. Graders are written from the contract and ticket only, never
from a reference patch. Tests are named `test_new__R<n>__...` or
`test_preserved__R<n>__...` (see AGENTS.md).

Grader file layout (one self-contained file):

    header        generated: DEMO_APP source, load_cli(), run()
    TESTS_MARK    tests a model writes from the contract and ticket
    PROBE_MARK    pivot tests generated from ticket-derived assertions

The demo app is kept as a string and built inside each test (via run()), so
on click without the feature the file still loads and each test fails with
a missing-API error rather than a collection error (which G1 rejects).
"""
from __future__ import annotations

import ast
import os
import re
import tempfile
from pathlib import Path

from factory.gates_basic import g4_public_api, parse_test_name
from factory.llm import llm, load_prompt
from factory.schema import Assertion, Contract, Finding, Invocation
from factory.validate.expect import derive_expectations, validate_assertion

TESTS_MARK = "# ---- tests written from the contract and ticket ----"
PROBE_MARK = "# ---- pivot tests: expectations derived from the ticket ----"
MAX_TRIES = 3  # first try + 2 retries
SKIP_ATTRS = {"skip", "skipif", "xfail", "importorskip"}

HEADER = '''"""Hidden grader for one ticket. Written from the contract and ticket only.

test_new__R<n>__...: new behaviour, fails on click without the feature.
test_preserved__R<n>__...: existing behaviour, passes on click without the feature.
"""
import types

import click
from click.testing import CliRunner

DEMO_APP = {demo}


def load_cli():
    """Build the demo app. On click without the feature this raises (missing API)."""
    ns = {{"__name__": "demo_app"}}
    exec(compile(DEMO_APP, "demo_app.py", "exec"), ns)
    return ns["cli"]


def run(argv, env=None, input=None):
    """Invoke the demo app; return an outcome with exit_code, output, exception_type."""
    result = CliRunner().invoke(load_cli(), argv, env=env or None, input=input)
    exc = result.exception
    return types.SimpleNamespace(
        exit_code=result.exit_code,
        output=result.output,
        exception_type=None if exc is None or isinstance(exc, SystemExit) else type(exc).__name__,
    )
'''


# ---- file assembly -----------------------------------------------------------

def _literal(src: str) -> str:
    """A readable triple-quoted literal for the demo app, falling back to repr()."""
    if "'''" in src or "\\" in src or src.endswith("'"):
        return repr(src)
    return f"'''{src}'''"


def assemble(contract: Contract, body: str, probe_tests: list[str]) -> str:
    """Full grader source: generated header, model-written tests, generated pivot tests."""
    parts = [HEADER.format(demo=_literal(contract.demo_app)).rstrip(),
             TESTS_MARK + "\n" + body.strip(),
             PROBE_MARK + "\n" + "\n\n\n".join(t.strip() for t in probe_tests if t.strip())]
    return "\n\n\n".join(parts) + "\n"


def _split(src: str) -> tuple[str, str]:
    """(model-written tests, pivot tests) from a grader in the factory layout."""
    if src.count(TESTS_MARK) != 1 or src.count(PROBE_MARK) != 1 or src.index(TESTS_MARK) > src.index(PROBE_MARK):
        raise ValueError("grader is not in the factory layout (missing section markers)")
    rest = src.split(TESTS_MARK, 1)[1]
    body, probes = rest.split(PROBE_MARK, 1)
    return body.strip(), probes.strip()


def _extract_python(text: str) -> str:
    blocks = re.findall(r"```(?:python|py)?[ \t]*\n(.*?)```", text, re.S)
    return max(blocks, key=len) if blocks else text


# ---- probe tests -------------------------------------------------------------

def _probe_test(assertions: list[Assertion], inv: Invocation, requirement_id: str, name: str) -> str:
    if not assertions:
        raise ValueError(f"no assertions for {requirement_id}: a pivot test must assert something")
    for a in assertions:
        if errors := validate_assertion(a):
            raise ValueError(f"invalid assertion {a.python!r}: {errors}")
    lines = [f"def test_new__{requirement_id}__{name}():",
             f"    outcome = run({inv.argv!r}, env={inv.env!r}, input={inv.input!r})"]
    lines += [f"    assert ({a.python}), {f'{a.requirement_id}: {a.description}'!r}" for a in assertions]
    return "\n".join(lines) + "\n"


def probe_test_source(assertions: list[Assertion], probe: Invocation, requirement_id: str) -> str:
    """Return pytest source for one `test_new__<req>__pivot_probe` test."""
    return _probe_test(assertions, probe, requirement_id, "pivot_probe")


# ---- checks ------------------------------------------------------------------

def _test_functions(tree: ast.Module) -> list[str]:
    names = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            names.append(node.name)
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            names += [n.name for n in node.body
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]
    return names


def check_grader_names(path: str, contract: Contract) -> list[str]:
    """Return naming/coverage problems in the grader at `path` (empty list = ok)."""
    try:
        tree = ast.parse(Path(path).read_text())
    except SyntaxError as e:
        return [f"syntax error on line {e.lineno}: {e.msg}"]
    errors: list[str] = []
    ids = {r.id for r in contract.requirements}
    names = _test_functions(tree)
    covered: dict[str, set[str]] = {}
    for name in sorted(set(names)):
        if names.count(name) > 1:
            errors.append(f"{name} is defined twice (the later one silently replaces the first)")
        kind, reqs = parse_test_name(f"grader.py::{name}")
        if kind == "other":
            errors.append(f"{name}: not named test_new__R<n>__... or test_preserved__R<n>__...")
            continue
        for r in reqs:
            if r not in ids:
                errors.append(f"{name}: unknown requirement {r} (contract has {sorted(ids)})")
            covered.setdefault(r, set()).add(kind)
    for r in sorted(ids - set(covered)):
        errors.append(f"requirement {r} has no test")
    pivot = contract.pivot().id
    if "new" not in covered.get(pivot, set()):
        errors.append(f"pivot requirement {pivot} has no test_new__ test")

    demo = [n for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "DEMO_APP" for t in n.targets)]
    if len(demo) != 1:
        errors.append(f"DEMO_APP must be assigned exactly once at top level (found {len(demo)})")
    elif not (isinstance(demo[0].value, ast.Constant) and isinstance(demo[0].value.value, str)
              and demo[0].value.value.strip() == contract.demo_app.strip()):
        errors.append("DEMO_APP does not match the contract's demo app")

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in SKIP_ATTRS:
            errors.append(f"line {node.lineno}: uses pytest {node.attr} (skipped/xfail tests count as errors)")
    return errors


def _check_source(src: str, contract: Contract, where: Path) -> list[str]:
    """Write `src` to a temp file next to `where` and run every grader check on it."""
    fd, tmp = tempfile.mkstemp(suffix=".py", dir=where.parent)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(src)
        errors = check_grader_names(tmp, contract)
        if not any(e.startswith("syntax error") for e in errors):
            errors += [f"private API: {h}" for h in g4_public_api(tmp).detail["private_uses"]]
        return errors
    finally:
        os.unlink(tmp)


def _contract_vars(contract: Contract, ticket: str) -> dict:
    return {
        "ticket": ticket,
        "requirements": "\n".join(f"- {r.id}{' (the rule this ticket is about)' if r.pivot else ''}: {r.text}"
                                  for r in contract.requirements),
        "open_items": "\n".join(f"- {x}" for x in contract.open_items) or "- (none)",
        "public_api": contract.public_api,
        "demo_app": contract.demo_app,
        "pivot_id": contract.pivot().id,
    }


def _ask_until_valid(prompt: str, role: str, contract: Contract, out: Path, probe_tests: list[str]) -> str:
    errors: list[str] = []
    for attempt in range(1, MAX_TRIES + 1):
        ask = prompt if not errors else (
            f"{prompt}\n\nAttempt {attempt} of {MAX_TRIES}. Your previous tests were rejected:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\nFix these and reply with the full tests section again, in one ```python block."
        )
        src = assemble(contract, _extract_python(llm(ask, role=role)), probe_tests)
        errors = _check_source(src, contract, out)
        if not errors:
            out.write_text(src)
            return str(out)
    raise ValueError(f"no valid grader after {MAX_TRIES} tries: {errors}")


# ---- generation and repair ---------------------------------------------------

def write_grader(contract: Contract, ticket: str, assertions: list[Assertion], out: Path) -> str:
    """Write a self-contained grader file to `out` and return its path."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    probe = probe_test_source(assertions, contract.probe, contract.pivot().id)
    prompt = load_prompt("validate", "grader", **_contract_vars(contract, ticket))
    return _ask_until_valid(prompt, "grader", contract, out, [probe])


def repair_grader(contract: Contract, ticket: str, grader_path: str, failure: str,
                  findings: list[Finding]) -> str:
    """Rewrite the grader using the failing gate's text and pivot findings; return its path.

    Each finding labelled "pivot" becomes a new test whose expectations come
    from `derive_expectations` on this ticket, never from either outcome.
    When `failure` is non-empty, a model also rewrites the tests section.
    """
    out = Path(grader_path)
    body, probes = _split(out.read_text())
    pivot = contract.pivot().id
    n = len(re.findall(rf"^def test_new__{pivot}__pivot_", probes, re.M)) + 1
    added = []
    for f in findings:
        if f.label != "pivot":
            continue
        assertions = derive_expectations(ticket, f.invocation, pivot)
        if assertions:
            added.append(_probe_test(assertions, f.invocation, pivot, f"pivot_case_{n}"))
            n += 1
    probe_tests = [probes, *added]

    if not failure.strip():
        src = assemble(contract, body, probe_tests)
        if errors := _check_source(src, contract, out):
            raise ValueError(f"repaired grader is invalid: {errors}")
        out.write_text(src)
        return str(out)

    prompt = load_prompt("validate", "repair_grader", **_contract_vars(contract, ticket),
                         failure=failure.strip(), tests=body)
    return _ask_until_valid(prompt, "repair_grader", contract, out, probe_tests)

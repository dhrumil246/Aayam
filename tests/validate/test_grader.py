import ast
import json
import types

import pytest

from factory.schema import Assertion, Finding, Invocation, Outcome
from factory.validate import grader

TICKET_A = "# Conflicting options\n\nR4: combining --json and --yaml is a usage error (exit 2) naming both.\n"

BODY = '''
def test_new__R1__option_accepts_conflicts_with():
    opt = click.Option(["--a"], conflicts_with=["b"])
    assert opt.name == "a"


def test_preserved__R2__single_flag_still_works():
    @click.command()
    @click.option("--json", "fmt", flag_value="json")
    def plain(fmt):
        click.echo(f"fmt={fmt}")
    result = CliRunner().invoke(plain, ["--json"])
    assert result.exit_code == 0 and "fmt=json" in result.output


def test_new__R2__single_flag_with_feature():
    outcome = run(["--json"])
    assert outcome.exit_code == 0 and "fmt=json" in outcome.output


def test_new__R3__unlisted_options_unaffected():
    outcome = run([])
    assert outcome.exit_code == 0
'''

ASSERTIONS = [Assertion("R4", "usage error", "outcome.exit_code == 2"),
              Assertion("R4", "names both", "'--json' in outcome.output and '--yaml' in outcome.output")]


def fenced(src: str) -> str:
    return f"Here are the tests:\n\n```python\n{src}\n```\n"


def write_sample(tmp_path, contract, body=BODY, name="test_A.py"):
    path = tmp_path / name
    path.write_text(grader.assemble(contract, body, [grader.probe_test_source(
        ASSERTIONS, contract.probe, "R4")]))
    return str(path)


# ---- probe_test_source -------------------------------------------------------

def test_probe_test_source():
    src = grader.probe_test_source(ASSERTIONS, Invocation(["--json", "--yaml"]), "R4")
    tree = ast.parse(src)
    [fn] = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert fn.name == "test_new__R4__pivot_probe"
    assert "['--json', '--yaml']" in src
    for a in ASSERTIONS:
        assert a.python in src


def test_probe_test_runs_against_fake_outcomes():
    """The generated test asserts each assertion: it passes on A's outcome and fails on B's."""
    src = grader.probe_test_source(ASSERTIONS, Invocation(["--json", "--yaml"], {"X": "1"}, "y\n"), "R4")
    seen = {}

    def run_a(argv, env=None, input=None):
        seen.update(argv=argv, env=env, input=input)
        return types.SimpleNamespace(exit_code=2, output="Error: --json conflicts with --yaml", exception_type=None)

    ns = {"run": run_a}
    exec(src, ns)
    ns["test_new__R4__pivot_probe"]()
    assert seen == {"argv": ["--json", "--yaml"], "env": {"X": "1"}, "input": "y\n"}

    ns["run"] = lambda argv, env=None, input=None: types.SimpleNamespace(exit_code=0, output="fmt=yaml",
                                                                      exception_type=None)
    with pytest.raises(AssertionError, match="usage error"):
        ns["test_new__R4__pivot_probe"]()


def test_probe_test_rejects_empty_or_invalid():
    with pytest.raises(ValueError):
        grader.probe_test_source([], Invocation(["--json"]), "R4")
    with pytest.raises(ValueError):
        grader.probe_test_source([Assertion("R4", "d", "__import__('os')")], Invocation([]), "R4")


# ---- assembled file ----------------------------------------------------------

def test_assembled_grader_runs_with_real_click(tmp_path, contract_a):
    """The header's run() works with the installed click (a plain demo app, no new feature)."""
    pytest.importorskip("click")
    contract_a.demo_app = 'import click\n\n@click.command()\n@click.option("--n", type=int)\ndef cli(n):\n    click.echo(f"n={n}")\n'
    path = write_sample(tmp_path, contract_a, body="")
    ns = {}
    exec(compile(open(path).read(), path, "exec"), ns)
    out = ns["run"](["--n", "3"])
    assert (out.exit_code, out.output, out.exception_type) == (0, "n=3\n", None)
    assert ns["run"](["--n", "x"]).exit_code == 2


def test_assembled_grader_missing_api_on_base(tmp_path, contract_a):
    """On click without the feature, building the demo app raises a missing-API TypeError, not an import error."""
    pytest.importorskip("click")
    path = write_sample(tmp_path, contract_a)
    ns = {}
    exec(compile(open(path).read(), path, "exec"), ns)  # the module itself always loads
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        ns["run"](["--json"])


# ---- check_grader_names ------------------------------------------------------

def test_names_sample_ok(tmp_path, contract_a):
    assert grader.check_grader_names(write_sample(tmp_path, contract_a), contract_a) == []


def test_names_unknown_requirement(tmp_path, contract_a):
    body = BODY + "\n\ndef test_new__R9__x():\n    assert run([]).exit_code == 0\n"
    errors = grader.check_grader_names(write_sample(tmp_path, contract_a, body), contract_a)
    assert any("R9" in e for e in errors)


def test_names_every_requirement_covered(tmp_path, contract_a):
    body = BODY.split("def test_new__R3__")[0]
    errors = grader.check_grader_names(write_sample(tmp_path, contract_a, body), contract_a)
    assert any("R3" in e for e in errors)


def test_names_unnamed_test(tmp_path, contract_a):
    body = BODY + "\n\ndef test_something():\n    assert True\n"
    errors = grader.check_grader_names(write_sample(tmp_path, contract_a, body), contract_a)
    assert any("test_something" in e for e in errors)


def test_names_duplicate(tmp_path, contract_a):
    body = BODY + "\n\ndef test_new__R3__unlisted_options_unaffected():\n    assert True\n"
    errors = grader.check_grader_names(write_sample(tmp_path, contract_a, body), contract_a)
    assert any("twice" in e for e in errors)


def test_names_skip_marker(tmp_path, contract_a):
    body = "import pytest\n\n@pytest.mark.skip\n" + BODY.lstrip()
    errors = grader.check_grader_names(write_sample(tmp_path, contract_a, body), contract_a)
    assert any("skip" in e for e in errors)


def test_names_demo_app_must_match(tmp_path, contract_a):
    path = write_sample(tmp_path, contract_a)
    contract_a.demo_app = contract_a.demo_app.replace("fmt=", "format=")
    assert any("DEMO_APP" in e for e in grader.check_grader_names(path, contract_a))


def test_names_syntax_error(tmp_path, contract_a):
    path = tmp_path / "bad.py"
    path.write_text("def (")
    assert grader.check_grader_names(str(path), contract_a) != []


# ---- write_grader ------------------------------------------------------------

def test_write_grader(fake_llm, tmp_path, contract_a):
    fake_llm["replies"] = [fenced(BODY)]
    out = tmp_path / "graders" / "test_A.py"
    path = grader.write_grader(contract_a, TICKET_A, ASSERTIONS, out)
    assert path == str(out)
    src = out.read_text()
    assert "test_new__R4__pivot_probe" in src and "test_preserved__R2__single_flag_still_works" in src
    assert grader.check_grader_names(path, contract_a) == []


def test_write_grader_prompt_has_no_reference(fake_llm, tmp_path, contract_a):
    fake_llm["replies"] = [fenced(BODY)]
    grader.write_grader(contract_a, TICKET_A, ASSERTIONS, tmp_path / "test_A.py")
    [prompt] = fake_llm["prompts"]
    assert TICKET_A in prompt
    assert "+++ b/" not in prompt
    assert "patch" not in prompt.lower()
    assert contract_a.pair_id not in prompt


def test_write_grader_retries_with_errors(fake_llm, tmp_path, contract_a):
    bad = BODY.split("def test_new__R3__")[0]  # R3 not covered
    fake_llm["replies"] = [fenced(bad), fenced(BODY)]
    path = grader.write_grader(contract_a, TICKET_A, ASSERTIONS, tmp_path / "test_A.py")
    assert grader.check_grader_names(path, contract_a) == []
    assert "R3" in fake_llm["prompts"][1]


def test_write_grader_rejects_private_api(fake_llm, tmp_path, contract_a):
    private = BODY + "\n\ndef test_new__R3__private():\n    assert click.core._missing is not None\n"
    fake_llm["replies"] = [fenced(private)] * 3
    with pytest.raises(ValueError, match="_missing"):
        grader.write_grader(contract_a, TICKET_A, ASSERTIONS, tmp_path / "test_A.py")


# ---- repair_grader -----------------------------------------------------------

def test_repair_adds_pivot_findings_from_ticket(fake_llm, tmp_path, contract_a):
    path = write_sample(tmp_path, contract_a)
    finding = Finding(Invocation(["--yaml", "--json"]), Outcome(0, "fmt=json"), Outcome(2, "Error"), label="pivot")
    shared = Finding(Invocation(["--json"]), Outcome(0, "a"), Outcome(0, "b"), label="shared")
    expectations = json.dumps([{"description": "usage error", "python": "outcome.exit_code == 2"}])
    fake_llm["replies"] = [expectations]  # no failure text, so no rewrite call
    assert grader.repair_grader(contract_a, TICKET_A, path, "", [finding, shared]) == path
    src = open(path).read()
    assert "test_new__R4__pivot_case_2" in src
    assert "['--yaml', '--json']" in src
    assert "test_new__R4__pivot_probe" in src  # existing probe test kept
    # The expectation came from the ticket prompt, not from either outcome.
    [prompt] = fake_llm["prompts"]
    assert TICKET_A in prompt and "fmt=json" not in prompt
    assert grader.check_grader_names(path, contract_a) == []


def test_repair_rewrites_tests_with_failure(fake_llm, tmp_path, contract_a):
    weak = BODY.replace('outcome.exit_code == 0 and "fmt=json" in outcome.output', "outcome.exit_code == 0")
    path = write_sample(tmp_path, contract_a, weak)
    fake_llm["replies"] = [fenced(BODY)]
    failure = "G1: test_new__R2__single_flag_with_feature passed on base"
    grader.repair_grader(contract_a, TICKET_A, path, failure, [])
    src = open(path).read()
    assert '"fmt=json" in outcome.output' in src
    assert "test_new__R4__pivot_probe" in src
    [prompt] = fake_llm["prompts"]
    assert failure in prompt and "test_new__R2__single_flag_with_feature" in prompt
    assert "patch" not in prompt.lower()


def test_repair_needs_factory_layout(tmp_path, contract_a):
    path = tmp_path / "test_A.py"
    path.write_text("def test_new__R1__x():\n    assert True\n")
    with pytest.raises(ValueError, match="layout"):
        grader.repair_grader(contract_a, TICKET_A, str(path), "G1 failed", [])

"""Uses tiny probe fixtures in tests/infra/data until the golden pair lands (then add golden cases)."""
from pathlib import Path

import pytest

from factory import sandbox
from factory import adapter_click
from factory.adapter_click import PIN

DATA = Path(__file__).parent / "data"
GRADER = str(DATA / "grader_probe.py")
P42, P41, GARBAGE = (str(DATA / n) for n in ("probe_42.patch", "probe_41.patch", "garbage.patch"))


def test_apply_check():
    assert sandbox.apply_check(PIN, P42)[0] is True
    ok, msg = sandbox.apply_check(PIN, GARBAGE)
    assert ok is False and msg


@pytest.mark.docker
def test_base_grader_fails_with_missing_api():
    run = sandbox.run_tests(PIN, [], [GRADER])
    new = [t for t in run.failed if "test_new__" in t]
    assert new and all(run.failed[t] == "missing_api" for t in new)
    assert any("test_preserved__" in t for t in run.passed)


@pytest.mark.docker
def test_ref_grader_passes():
    run = sandbox.run_tests(PIN, [P42], [GRADER])
    assert run.failed == {}
    assert len(run.passed) == 2


@pytest.mark.docker
def test_wrong_patch_is_assertion():
    run = sandbox.run_tests(PIN, [P41], [GRADER])
    assert [k for t, k in run.failed.items() if "test_new__" in t] == ["assertion"]


@pytest.mark.docker
def test_bad_patch():
    run = sandbox.run_tests(PIN, [GARBAGE], [GRADER])
    assert run.passed == [] and set(run.failed.values()) == {"error"}
    assert "git apply" in Path(run.log_path).read_text()


@pytest.mark.docker
def test_syntax_error_is_collection():
    run = sandbox.run_tests(PIN, [], [str(DATA / "grader_syntax_error.py")])
    assert set(run.failed.values()) == {"collection"}


@pytest.mark.docker
def test_repeat_requires_every_run_to_pass():
    run = sandbox.run_tests(PIN, [P42], [GRADER], repeat=2)
    assert run.failed == {} and len(run.passed) == 2


@pytest.mark.docker
def test_existing_suite_on_patch_skips_excluded():
    run = sandbox.run_tests(PIN, [P42])
    assert run.failed == {}  # the 24 `less` pager tests fail on this image, so this proves they are excluded
    assert not any(adapter_click.is_excluded(t) for t in run.passed)
    assert len(run.passed) > 2000


def test_classify():
    assert sandbox._classify("x.py:3: AttributeError") == "missing_api"
    assert sandbox._classify("E   TypeError: f() got an unexpected keyword argument 'x'\nx.py:3: TypeError") == "missing_api"
    assert sandbox._classify("E   TypeError: bad\nx.py:3: TypeError") == "error"
    assert sandbox._classify("E   assert 41 == 42\nx.py:5: AssertionError") == "assertion"
    assert sandbox._classify("x.py:5: ValueError") == "error"


def _containers() -> str:
    import subprocess
    return subprocess.run(["docker", "ps", "-q", "--filter", f"ancestor={adapter_click.image(PIN)}"], capture_output=True, text=True).stdout.strip()


@pytest.mark.docker
def test_crashed_pytest_is_error_not_pass():
    run = sandbox.run_tests(PIN, [str(DATA / "broken_testing.patch")])
    assert run.failed and set(run.failed.values()) == {"error"}


@pytest.mark.docker
def test_skip_and_xfail_count_as_error_in_graders():
    run = sandbox.run_tests(PIN, [], [str(DATA / "grader_skips.py")])
    bad = {t.split("::")[-1]: k for t, k in run.failed.items()}
    assert bad == {"test_new__R1__skipped": "error", "test_new__R1__xfailed": "error", "test_new__R1__xpassed": "error"}
    assert [t.split("::")[-1] for t in run.passed] == ["test_preserved__R2__runs"]


@pytest.mark.docker
def test_run_tests_timeout_kills_container():
    run = sandbox.run_tests(PIN, [], [str(DATA / "grader_hang.py")], timeout=8)
    assert set(run.failed.values()) == {"error"}
    assert _containers() == ""

"""Probe fixtures from tests/infra/data until the golden pair lands."""
import time
from pathlib import Path

import pytest

from factory.adapter_click import PIN
from factory.schema import Invocation, Outcome
from factory.worker import Worker, fresh_call

DATA = Path(__file__).parent / "data"
P42, P41 = str(DATA / "probe_42.patch"), str(DATA / "probe_41.patch")
DEMO = '''
import click

@click.command()
@click.option("--n", default=1, type=int)
def cli(n):
    click.echo(f"probe={click.factory_probe() * n}")
'''
PROBE = Invocation(["--n", "2"])

pytestmark = pytest.mark.docker


def test_probe_patched():
    with Worker(PIN, P42, DEMO) as w:
        assert w.call(PROBE) == Outcome(0, "probe=84\n", None)
        assert w.call(Invocation(["--n", "x"])).exit_code == 2


def test_two_patches_differ():
    assert fresh_call(PIN, P42, DEMO, PROBE) != fresh_call(PIN, P41, DEMO, PROBE)


def test_base_reports_missing_api():
    out = fresh_call(PIN, None, DEMO, PROBE)
    assert out.exit_code == 1 and out.exception_type == "AttributeError"


def test_fresh_matches_persistent():
    with Worker(PIN, P42, DEMO) as w:
        assert w.call(PROBE) == fresh_call(PIN, P42, DEMO, PROBE)


def test_no_state_between_calls():
    demo = "import click\nCOUNT = [0]\n@click.command()\ndef cli():\n    COUNT[0] += 1\n    click.echo(COUNT[0])\n"
    with Worker(PIN, None, demo) as w:
        assert w.call(Invocation([])).output == w.call(Invocation([])).output == "1\n"


def test_env_and_stdin():
    demo = ("import click\n@click.command()\n@click.option('--name', envvar='APP_NAME', prompt=True)\n"
            "def cli(name):\n    click.echo(f'hi {name}')\n")
    with Worker(PIN, None, demo) as w:
        assert w.call(Invocation([], env={"APP_NAME": "ana"})).output == "hi ana\n"
        assert w.call(Invocation([], input="ben\n")).output.endswith("hi ben\n")


def test_timeout_then_recovers():
    demo = "import click, time\n@click.command()\n@click.option('--wait', is_flag=True)\ndef cli(wait):\n    time.sleep(30 if wait else 0)\n    click.echo('ok')\n"
    with Worker(PIN, None, demo) as w:
        w.call(Invocation([]))  # warm: the start-up grace no longer applies
        t = time.monotonic()
        assert w.call(Invocation(["--wait"]), timeout=3) == Outcome(-1, "", "Timeout")
        assert time.monotonic() - t < 6
        assert w.call(Invocation([])).output == "ok\n"

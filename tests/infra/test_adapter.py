import json
import re
from pathlib import Path

import pytest

from factory import adapter_click

ROOT = Path(__file__).resolve().parents[2]


def test_pin_complete():
    pin = json.loads((ROOT / "factory" / "pin.json").read_text())
    assert pin["repo"] == "pallets/click"
    assert re.fullmatch(r"[0-9a-f]{40}", pin["sha"])
    assert "@sha256:" in pin["base_image"]
    assert adapter_click.BASE_IMAGE == pin["base_image"]
    assert adapter_click.PIN.sha == pin["sha"]
    dockerfile = (ROOT / "docker" / "click.Dockerfile").read_text()
    assert f"FROM {pin['base_image']}" in dockerfile.splitlines()
    lock = (ROOT / "docker" / "requirements.lock").read_text().splitlines()
    pkgs = [l for l in lock if l and not l.startswith((" ", "#"))]
    assert pkgs, "lock file names no packages"
    for line in pkgs:
        assert "--hash=" in line or line.rstrip().endswith("\\"), line
    assert "--hash=sha256:" in "\n".join(lock)


@pytest.mark.docker
def test_g0_baseline():
    from factory.gates_basic import g0_baseline
    result = g0_baseline(adapter_click.PIN)
    assert result.gate == "G0"
    assert result.passed is True, result.detail
    assert result.detail["failed"] == []


def test_env_excluded_tests():
    assert adapter_click.is_excluded("tests/test_utils/test_echo_via_pager.py::test_echo_via_pager[test0- less ]")
    assert not adapter_click.is_excluded("tests/test_utils/test_echo_via_pager.py::test_echo_via_pager[test0-cat]")
    assert not adapter_click.is_excluded("tests/test_basic.py::test_basic_functionality")
    for reason in adapter_click.ENV_EXCLUDED.values():
        assert reason

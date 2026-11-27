"""The validate interfaces exist with the agreed names (real tests replace this later)."""
import importlib

import pytest

PRODUCES = {
    "expect": ["derive_expectations", "validate_assertion", "check"],
    "grader": ["write_grader", "check_grader_names", "repair_grader", "probe_test_source"],
    "probe": ["g5_twin_separation"],
    "search": ["invocations", "diff_search", "classify_finding"],
    "mutants": ["make_mutants", "g6_mutants"],
    "trace": ["g7_trace"],
}


@pytest.mark.parametrize("module,names", PRODUCES.items())
def test_validate_interfaces_exist(module, names):
    mod = importlib.import_module(f"factory.validate.{module}")
    for name in names:
        assert callable(getattr(mod, name)), f"{module}.{name} missing"

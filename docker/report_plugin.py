"""pytest plugin loaded inside the sandbox: one JSON line per outcome, with exact node ids."""
import json
import os

OUT = os.environ.get("FACTORY_REPORT", "/out/report.jsonl")


def _write(row):
    with open(OUT, "a") as f:
        f.write(json.dumps(row) + "\n")


def pytest_collectreport(report):
    if report.failed:
        _write({"nodeid": report.nodeid, "when": "collect", "outcome": "failed", "longrepr": str(report.longrepr)})


def pytest_runtest_logreport(report):
    if report.when == "call" or report.outcome != "passed":
        _write({"nodeid": report.nodeid, "when": report.when, "outcome": report.outcome,
                "xfail": hasattr(report, "wasxfail"),
                "longrepr": str(report.longrepr) if report.failed else ""})

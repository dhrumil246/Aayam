"""`python -m factory ...` Owner: Dhrumil.

argparse (stdlib), not click, so the factory's own CLI never mixes with the click under test.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

from factory import adapter_click, pipeline
from factory.schema import Pair, load

FAMILIES = ["conflict", "precedence", "repetition", "validation", "lifecycle", "deprecation", "retry"]
HEET = {"export_pair": "factory.export:export_pair", "replay": "factory.export:replay",
        "build_report": "factory.report.build:build_report"}


def _heet(name: str):
    module, fn = HEET[name].split(":")
    return getattr(importlib.import_module(module), fn)


def _pairs(ids: list[str], all_: bool) -> list[Pair]:
    root = adapter_click._runs()
    if all_:
        found = [load(Pair, p) for p in sorted(root.glob("*/pair.json"))]
        return [p for p in found if p.status == "accepted"]
    return [load(Pair, root / i / "pair.json") for i in ids]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="factory", description="Twin-ticket task factory for pallets/click")
    sub = ap.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="generate and validate twin pairs")
    g.add_argument("--family", required=True, choices=FAMILIES)
    g.add_argument("--n", type=int, default=1, help="how many pairs to attempt")
    g.add_argument("--pair-id", help="resume (or name) this pair")

    e = sub.add_parser("evaluate", help="blind-solve a pair's tickets and diagnose")
    e.add_argument("pair_id")
    e.add_argument("--models", required=True, help="comma-separated model ids")

    x = sub.add_parser("export", help="write task packages")
    x.add_argument("pair_ids", nargs="*")
    x.add_argument("--all", action="store_true", help="every accepted pair")
    x.add_argument("--out", default="packages")

    r = sub.add_parser("report", help="build the static evidence report")
    r.add_argument("--out", default="report/index.html")

    p = sub.add_parser("replay", help="re-run a package's evidence with no model calls")
    p.add_argument("package_dir")

    a = ap.parse_args(argv)

    if a.cmd == "generate":
        for _ in range(a.n):
            pair = pipeline.run_pair(a.family, adapter_click.PIN, a.pair_id)
            print(f"{pair.seed.pair_id}: {pair.status}" + (f" ({pair.reject_reason})" if pair.reject_reason else ""))
        return 0
    if a.cmd == "evaluate":
        pipeline.evaluate_pair(a.pair_id, [m.strip() for m in a.models.split(",") if m.strip()])
        return 0
    if a.cmd == "export":
        if not a.all and not a.pair_ids:
            ap.error("export needs pair ids or --all")
        for pair in _pairs(a.pair_ids, a.all):
            _heet("export_pair")(pair, Path(a.out))
            print(f"exported {pair.seed.pair_id}")
        return 0
    if a.cmd == "report":
        print(_heet("build_report")(adapter_click._runs(), Path(a.out)))
        return 0
    result = _heet("replay")(Path(a.package_dir))
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("matches") else 1


if __name__ == "__main__":
    sys.exit(main())

"""Worker loop inside the sandbox: one JSON request per line in, one JSON outcome per line out.

The demo app is re-executed for every call, so no state carries between calls.
"""
import json
import sys
import traceback

from click.testing import CliRunner

SOURCE = open("/demo/app.py").read()
out = sys.stdout

for line in sys.stdin:
    req = json.loads(line)
    try:
        ns = {"__name__": "demo_app"}
        exec(compile(SOURCE, "demo_app.py", "exec"), ns)
        r = CliRunner().invoke(ns["cli"], req["argv"], env=req.get("env") or None, input=req.get("input"))
        exc = r.exception
        res = {"exit_code": r.exit_code, "output": r.output,
               "exception_type": None if exc is None or isinstance(exc, SystemExit) else type(exc).__name__}
    except Exception as e:  # demo app itself failed to load
        res = {"exit_code": -1, "output": traceback.format_exc(), "exception_type": type(e).__name__}
    out.write(json.dumps(res) + "\n")
    out.flush()

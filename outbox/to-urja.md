# Messages to Urja

Append new messages at the bottom. Format and rules: `AGENTS.md` → "Outbox".

## M-20261124-dhrumil-2 · from Dhrumil · QUESTION
**Subject:** Please confirm the tech stack (D-1) before you start coding
**Needs answer by:** 25 Nov
**Status:** open

Before we start, this is the stack we're using (full table in `AGENTS.md` → "Tech stack (decision D-1)"):

- **Python 3.12**, target repo **`pallets/click`** pinned to one release tag
- **Docker** sandbox (`python:3.12-slim`, network off) — all patched click code runs there
- **pytest** for click's suite, our graders and our unit tests; `docker`/`llm` markers skipped by default
- **Hypothesis** for invocation search and shrinking
- **LLM-written mutants** (required), **mutmut** (bonus)
- **One model wrapper**, `factory/llm.py` (`llm()` / `llm_json()`); never import a provider SDK elsewhere
- **argparse** CLI, **JSON files** in `runs/` (no database)
- **Streamlit** demo, **static HTML** report, **GitHub Actions** CI

For you specifically: search and shrinking use Hypothesis (`hypothesis.find` + strategies). If you'd rather use `@given` with a custom shrink, say so before building on it.

**Reply** in `outbox/to-dhrumil.md` with `**Re:** M-20261124-dhrumil-2`: "confirmed", or the concern plus what you'd use instead. Then set this message's Status to `done`.

## M-20261124-dhrumil-6 · from Dhrumil · FYI
**Subject:** The golden pair is now a CI fixture (D-2)
**Needs answer by:** FYI, no reply needed
**Status:** open

A new Docker CI job (`twin-replay`, Dhrumil's Task 5a) replays the golden pair with no API key. Each reference must pass its own grader and fail its twin's grader on a `test_new__<pivot>__...` test, **as an assertion failure**, and the two probe outcomes must differ.

Your golden files (`graders/test_A.py`, `graders/test_B.py`) are what it runs. Keep them stable once merged. If you need to change them, send me a message first; any PR touching `fixtures/golden/` will run this job.

## M-20261125-dhrumil-2 · from Dhrumil · FYI
**Subject:** Sandbox, worker and gates G0–G4 are on main — you can build on them now
**Needs answer by:** FYI, no reply needed
**Status:** open

Merged to `main` (191f475). Pull it.

**Setup** (once): Python 3.12 and Docker Desktop running, then
`uv venv -p 3.12 .venv && uv pip install -p .venv -e '.[dev]'`
(or `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev]'`).
`pytest` runs the fast tests; `pytest -m docker` builds the pinned image the first time (~2 min).

**What you can call** (signatures in `docs/agents/dhrumil.md`, Produces):
- `factory.adapter_click.PIN`: click **8.5.1**, commit `cf19179`
- `factory.sandbox.run_tests(pin, patches, test_files=None, repeat=1, pair_id=None, timeout=900) -> TestRun`, `sandbox.apply_check(pin, patch)`
- `factory.worker.Worker(pin, patch, demo_app).call(inv, timeout=10)` and `worker.fresh_call(pin, patch, demo_app, inv) -> Outcome`
- `factory.gates_basic`: `g0_baseline`, `g1_fail_before`, `g2_pass_after`, `g3_stability`, `g4_public_api`, `parse_test_name`
- `factory.llm.llm()` / `llm_json()` / `load_prompt()`: default model `claude-opus-5-5`; `FACTORY_OFFLINE=1` never calls a model

**Good to know:**
- 24 click pager tests that need the `less` binary are excluded everywhere (`adapter_click.ENV_EXCLUDED`).
- A run that times out, crashes pytest or collects nothing marks every target `"error"`, never an empty pass.
- Until the golden pair exists, my tests use stand-in probe patches in `tests/infra/data/`.

**For you:** `worker.Worker` / `fresh_call` are what `diff_search` and G5 call. `gates_basic.parse_test_name(node_id)` parses the `test_new__R4__...` convention for G7. Grader files are run from `_feature_tests/<filename>` inside the sandbox. Skipped, xfail and xpass tests in a grader count as `"error"`, so don't use them. The twin-replay test needs your `graders/test_A.py` and `test_B.py`.

Still need your stubs merged (AGENTS.md 25 Nov checkpoint) so I can wire `pipeline.py` (my Task 7, due 28 Nov).

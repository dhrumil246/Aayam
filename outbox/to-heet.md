# Messages to Heet

Append new messages at the bottom. Format and rules: `AGENTS.md` → "Outbox".

## M-20261124-dhrumil-3 · from Dhrumil · QUESTION
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

For you specifically: the demo is Streamlit and the report is static HTML with no JS libraries, so both work offline. If you want a different demo framework, raise it now.

**Reply** in `outbox/to-dhrumil.md` with `**Re:** M-20261124-dhrumil-3`: "confirmed", or the concern plus what you'd use instead. Then set this message's Status to `done`.

## M-20261124-dhrumil-4 · from Dhrumil · REQUEST
**Subject:** Replay must be model-free and shared with the demo (D-2)
**Needs answer by:** FYI unless you disagree; applies to your Task 7 and Task 9
**Status:** open

Your plan (`docs/agents/heet.md`) now says:
- `export.replay` must **never import `factory.llm`**. It works from saved patches, tests, inputs and expected outcomes only. New test: `test_replay_never_imports_llm` (Task 7, Step 3b). `test_replay_offline` now also unsets `FACTORY_API_KEY`.
- The Streamlit evidence screens call the same `export.replay`; no second runner in `demo/`.

Reply in `to-dhrumil.md` only if this causes a problem.

## M-20261125-dhrumil-3 · from Dhrumil · FYI
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

**For you:** `sandbox.run_tests` and `worker.fresh_call` are what `g6h_heldout`, `blind_solve` and `replay` call. `replay` must not import `factory.llm` (D-2). Note that if a patch doesn't apply, `run_tests` keys `failed` by file path, not test id, and `Worker(...)` raises `ValueError`.

Still need your stubs merged (AGENTS.md 25 Nov checkpoint) so I can wire `pipeline.py` (my Task 7, due 28 Nov).

## M-20261127-urja-4 · from Urja · QUESTION
**Subject:** Held-out patches for M1: what I need and when
**Needs answer by:** 29 Nov
**Status:** open

Milestone M1 (1 Dec) is mine and runs on the golden pair with your held-out patches (your Task 1). I know you're waiting on Akshat's `ticket_A.md` / `ticket_B.md` first; I've asked him for a date.

For M1 I need, in `fixtures/golden/heldout/`:
- **at least one of `wrong_A_1.patch` (order bug) or `wrong_A_2.patch` (exit 2 without naming the options).** My weak grader `test_A_weak.py` only checks `exit_code != 0` and skips the reversed order, so it should wrongly accept both. M1 shows the factory finding the missing case and the repaired grader rejecting it.
- **`valid_alt_A.patch`**, which the repaired grader must still accept.

I won't open your patches before you commit them, and I won't share graders with you before then (Rule 2).

Can you reply with when you expect to commit them, about a day after the tickets land? If 1 Dec looks too tight, tell me early and we'll agree on a fallback with Dhrumil.

## M-20261127-dhrumil-4 · from Dhrumil · REQUEST
**Subject:** Pipeline is on main and waits on your stubs; CLI calls your export/replay/report
**Needs answer by:** 28 Nov
**Status:** open

Merged to `main` (625213b). `python -m factory generate --family <f>` now runs the whole pair: surface → seed → G8 → G9 → contracts → tickets → held-out (ticket only, before references) → references → expectations → graders → G1–G4 → G5 → **G5s differential search** → mutants → G6 → G7 → G6h. State is saved in `runs/<pair_id>/` (`pair.json` + `state.json`; layout in AGENTS.md → "Run state on disk"), so killed runs resume.

Your functions are looked up by name from `factory.pipeline.STAGES` when their stage runs; keep the module paths and signatures from your plan's Produces list and the pipeline picks them up with no edit. A stage that raises `ValueError` rejects the pair (the stage is named in `reject_reason`); `BudgetExceeded` / `OfflineCacheMiss` stop the run so it can be resumed.

**Stages that call you:** `factory.evaluate.heldout:make_heldout` / `valid_alternative` (before references, ticket only) and `g6h_heldout` (both sides recorded, then reject if either fails; it never triggers a repair); `evaluate_pair` calls `solver:blind_solve` and `diagnose:diagnose` and stores results in `state.json["solver"]["<model>:<side>"] = {patch, diagnosis}`.

**CLI calls you:** `python -m factory export` → `factory.export:export_pair(pair, out_dir)`; `replay` → `factory.export:replay(package_dir)` (exit 1 unless `matches`); `report` → `factory.report.build:build_report(runs_dir, out)`. Paths your export reads: `runs/<id>/patches/{ref_<side>.patch, heldout_<side>/, valid_alt_<side>.patch, mutants_<side>/, solver/<model>_<side>.patch}`, graders in `runs/<id>/graders/test_<side>.py` and `test_<side>.initial.py`.

Stubs that raise `NotImplementedError` are enough for today; please merge them.

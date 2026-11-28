# Messages to Akshat

Append new messages at the bottom. Format and rules: `AGENTS.md` → "Outbox".

## M-20261124-dhrumil-1 · from Dhrumil · QUESTION
**Subject:** Please confirm the tech stack (D-1) before you start coding
**Needs answer by:** 25 Nov
**Status:** done

Before we start, this is the stack we're using (full table in `AGENTS.md` → "Tech stack (decision D-1)"):

- **Python 3.12**, target repo **`pallets/click`** pinned to one release tag
- **Docker** sandbox (`python:3.12-slim`, network off) — all patched click code runs there
- **pytest** for click's suite, our graders and our unit tests; `docker`/`llm` markers skipped by default
- **Hypothesis** for invocation search and shrinking
- **LLM-written mutants** (required), **mutmut** (bonus)
- **One model wrapper**, `factory/llm.py` (`llm()` / `llm_json()`); never import a provider SDK elsewhere
- **argparse** CLI, **JSON files** in `runs/` (no database)
- **Streamlit** demo, **static HTML** report, **GitHub Actions** CI

For you specifically: reference patches and the novelty check run through `factory.sandbox` and `gh` (optional). If the reference agent loop needs another library, ask before using it.

**Reply** in `outbox/to-dhrumil.md` with `**Re:** M-20261124-dhrumil-1`: "confirmed", or the concern plus what you'd use instead. Then set this message's Status to `done`.

## M-20261124-dhrumil-5 · from Dhrumil · FYI
**Subject:** The golden pair is now a CI fixture (D-2)
**Needs answer by:** FYI, no reply needed
**Status:** open

A new Docker CI job (`twin-replay`, Dhrumil's Task 5a) replays the golden pair with no API key. Each reference must pass its own grader and fail its twin's grader on a `test_new__<pivot>__...` test, **as an assertion failure**, and the two probe outcomes must differ.

Your golden files (`ref_A.patch`, `ref_B.patch`, `contract_A/B.json`, `demo_app.py`) are what it runs. Keep them stable once merged. If you need to change them, send me a message first; any PR touching `fixtures/golden/` will run this job.

## M-20261125-dhrumil-1 · from Dhrumil · FYI
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

**For you:** `write_reference` can now use `sandbox.apply_check` and `sandbox.run_tests(PIN, [patch])` (existing suite), plus `worker.fresh_call` for the probe smoke check. The golden pair (`fixtures/golden/`) is the next blocker for everyone: the twin-replay test and CI job are ready and will start running once your `contract_A/B.json`, `ref_A/B.patch` and `demo_app.py` land.

Still need your stubs merged (AGENTS.md 25 Nov checkpoint) so I can wire `pipeline.py` (my Task 7, due 28 Nov).

## M-20261127-urja-3 · from Urja · BLOCKER
**Subject:** When will the golden pair land? M1 (1 Dec) and twin-replay are waiting on it
**Needs answer by:** 28 Nov
**Status:** done

`fixtures/golden/` is still empty on `main` (it was due 25 Nov). My validate code is merged (PR #2), so the golden pair is now the only thing stopping me from:

- writing and checking the golden graders `fixtures/golden/graders/test_A.py`, `test_B.py` and the weak M1 grader `test_A_weak.py`;
- running G5 and differential search on real patches;
- Milestone M1 on 1 Dec, which runs on the golden pair.

Heet also needs your `ticket_A.md` / `ticket_B.md` to write the held-out patches, and Dhrumil's twin-replay CI job is waiting on `contract_A/B.json`, `ref_A/B.patch` and `demo_app.py`.

What I need from you, in this order if you can split it:
1. `contract_A.json`, `contract_B.json`, `demo_app.py`, `ticket_A.md`, `ticket_B.md` (enough for me to write graders and for Heet to start)
2. `ref_A.patch`, `ref_B.patch`

Please reply with a date, or tell me if something is stuck (novelty check, the patches, anything) and I'll help where I can without touching your files.

## M-20261127-dhrumil-2 · from Dhrumil · REQUEST
**Subject:** Pipeline is on main and waits on your stubs + golden pair
**Needs answer by:** 28 Nov
**Status:** done

Merged to `main` (625213b). `python -m factory generate --family <f>` now runs the whole pair: surface → seed → G8 → G9 → contracts → tickets → held-out (ticket only, before references) → references → expectations → graders → G1–G4 → G5 → **G5s differential search** → mutants → G6 → G7 → G6h. State is saved in `runs/<pair_id>/` (`pair.json` + `state.json`; layout in AGENTS.md → "Run state on disk"), so killed runs resume.

Your functions are looked up by name from `factory.pipeline.STAGES` when their stage runs; keep the module paths and signatures from your plan's Produces list and the pipeline picks them up with no edit. A stage that raises `ValueError` rejects the pair (the stage is named in `reject_reason`); `BudgetExceeded` / `OfflineCacheMiss` stop the run so it can be resumed.

**You are now the blocker for the first end-to-end run.** `generate` fails at the first stage until these exist with your planned signatures: `factory.propose.surface:discover_surface`, `seeds:propose_seed`, `novelty:novelty_gate`, `realism:realism_gate`, `contract:write_contracts`, `ticket:render_ticket`, `reference:write_reference` / `repair_reference`. Stubs that raise `NotImplementedError` are enough for today; the golden pair in `fixtures/golden/` unblocks the twin-replay CI job, Urja's golden graders and M1 (1 Dec).

Notes: `write_contracts` raising `ValueError` after its retries is handled (pair rejected). `repair_reference` is now also called on **both** sides when differential search finds a case where a reference breaks a shared requirement; the failure text includes those findings.

# Dhrumil: Repo, Execution & Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `AGENTS.md` first. Edit only files listed under **Files** below.

**Goal:** The critical path: the repo skeleton, model-call wrapper, Docker sandbox, worker, basic gates G0–G4, the pipeline that calls everyone's functions, and the CLI. (Export and offline replay belong to Heet.)

**Architecture:** Python 3.12 package `factory/`. Patched click always runs in Docker (`python:3.12-slim`, network off). Others never call Docker directly; they call `sandbox.run_tests()` and `worker.Worker`. You are the only person who edits `pipeline.py`, so integration conflicts land with you by design.

**Tech Stack:** Python 3.12, Docker, pytest (junit XML), argparse, provider SDK (one file only).

**Spec:** `docs/design.md` (§7 pipeline, §8 G0–G4, §13 stack).

## Global Constraints
- Base revision: from the provided starter kit; otherwise latest stable click release tag, recorded in `factory/pin.json` on 24 Nov.
- No API keys in the repo. Keys only from env: `FACTORY_API_KEY`, `FACTORY_PROVIDER`, `FACTORY_MODEL_DEFAULT`.
- `FACTORY_OFFLINE=1` must make every command run with zero model calls (cache only).
- Per-pair cost cap: `FACTORY_PAIR_BUDGET_USD`, default `5`.
- Tests run with `network=none` inside the container.
- Default `pytest` run needs no Docker and no key.

## Review Focus
1. A patch that doesn't apply cleanly: `run_tests` must return a `TestRun` with every requested test marked `"error"` and the `git apply` message in the log, not crash.
2. A test file with a syntax error: classified `"collection"`, never `"assertion"` or `"missing_api"` (G1 depends on this).
3. A demo app that hangs on stdin: worker call must time out (10 s) and return `Outcome(exit_code=-1, exception_type="Timeout")`.
4. Cache-miss in offline mode: a clear `OfflineCacheMiss` naming the role and pair, not a provider auth error.
5. Re-running `factory generate` on an existing `pair_id`: resume from the last saved stage, don't overwrite accepted pairs.

---

### Task 1: Repo skeleton (24 Nov, first thing)

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.github/workflows/ci.yml`, `factory/__init__.py`, `tests/infra/test_schema.py`
- Commit as provided: `factory/schema.py`, `AGENTS.md`, `CLAUDE.md`, `docs/`

**Interfaces:**
- Produces: package `factory`; pytest markers `docker`, `llm`; `addopts = "-m 'not docker and not llm'"`.

- [ ] **Step 1: Write the test** `test_schema_roundtrip`: build a `Pair` with one `Contract`, `save()` then `load(Pair, ...)`, assert equal and `pivot().id == "R2"`. (Same as `schema.py`'s `__main__` block.)
- [ ] **Step 2: Run** `pytest tests/infra -v`. Expected: PASS.
- [ ] **Step 3: Add** `.gitignore` with `runs/`, `.venv/`, `__pycache__/`; CI runs `pip install -e .[dev] && pytest` on PRs.
- [ ] **Step 4: Create empty owner folders** with `__init__.py`: `factory/propose/`, `factory/validate/`, `factory/evaluate/`, `factory/report/`, plus `prompts/{propose,validate,evaluate}/`, `demo/`, `fixtures/golden/`. Push; tell the team to branch.
- [ ] **Step 5: Commit** `chore: repo skeleton, schema, agent docs`.

### Task 2: `llm.py`: the only door to a model

**Files:** Create `factory/llm.py`, `tests/infra/test_llm.py`

**Interfaces:**
- Produces:
  - `llm(prompt: str, *, role: str, model: str | None = None, pair_id: str | None = None, temperature: float = 0.0) -> str`
  - `llm_json(prompt: str, *, role: str, model: str | None = None, pair_id: str | None = None) -> dict | list` (strips ```json fences, one retry on parse failure)
  - `load_prompt(area: str, name: str, **vars) -> str` (reads `prompts/<area>/<name>.md`, `str.format_map(vars)`)
  - exceptions `OfflineCacheMiss`, `BudgetExceeded`

- [ ] **Step 1: Write failing tests** with a fake provider monkeypatched over `_call`:
  - `test_cache_hit_offline`: call once online, set `FACTORY_OFFLINE=1`, same call returns the same text and `_call` isn't invoked again.
  - `test_cache_miss_offline_raises`: `pytest.raises(OfflineCacheMiss)`, message contains the role.
  - `test_costs_logged`: one line in `runs/costs.jsonl` with keys `ts, role, model, pair_id, in_tokens, out_tokens, usd`.
  - `test_budget`: with `FACTORY_PAIR_BUDGET_USD=0.0001`, second call for the same `pair_id` raises `BudgetExceeded`.
  - `test_llm_json_fenced`: fake returns "```json\n{\"a\":1}\n```" → `{"a": 1}`.
- [ ] **Step 2: Run** `pytest tests/infra/test_llm.py -v`. Expected: FAIL (module missing).
- [ ] **Step 3: Implement.** Cache key = sha256 of `model + "\n" + str(temperature) + "\n" + prompt`; file `runs/llm_cache/<key>.json`. Provider chosen by `FACTORY_PROVIDER` inside a single `_call(prompt, model, temperature) -> (text, in_tokens, out_tokens)`. Price table as a dict at the top of the file.
- [ ] **Step 4: Run** tests. Expected: PASS. One `@pytest.mark.llm` smoke test with a real key; paste output in the PR.
- [ ] **Step 5: Commit** `feat(llm): cached, costed, offline-capable model calls`.

### Task 3: Click adapter + Docker image + G0

**Files:** Create `factory/pin.json`, `factory/adapter_click.py`, `docker/click.Dockerfile`, `factory/gates_basic.py` (G0 only for now), `tests/infra/test_adapter.py`

**Interfaces:**
- Produces:
  - `adapter_click.PIN: RepoPin` (loaded from `pin.json`)
  - `adapter_click.repo_dir(pin) -> Path` (clone cache at `runs/repos/<sha>/`)
  - `adapter_click.image(pin) -> str` (builds once, tag `factory-click:<sha[:12]>`)
  - `adapter_click.EXISTING_TESTS = "tests/"`, `adapter_click.FLAKY: list[str]` (filled from baseline)
  - `gates_basic.g0_baseline(pin: RepoPin) -> GateResult`

- [ ] **Step 1: Pick the pin.** Starter-kit revision if given; else `git ls-remote --tags https://github.com/pallets/click` → latest stable. Write `pin.json` `{repo, tag, sha}`.
- [ ] **Step 2: Write failing test** `test_g0_baseline` (`@pytest.mark.docker`): `g0_baseline(PIN).passed is True` and `detail["failed"] == []` after excluding `FLAKY`.
- [ ] **Step 3: Implement.** Dockerfile: checkout at sha, `pip install -e . pytest hypothesis`. G0 runs the existing suite 3× and records any test that flips as `FLAKY` (written to `factory/flaky.json`).
- [ ] **Step 4: Run** `pytest -m docker tests/infra/test_adapter.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** `feat(adapter): pinned click image and G0 baseline`.

### Task 4: `sandbox.py`: run tests on a patched checkout (due 25 Nov, everyone needs it)

**Files:** Create `factory/sandbox.py`, `tests/infra/test_sandbox.py`

**Interfaces:**
- Consumes: `adapter_click.image`, `PIN`.
- Produces:
  - `apply_check(pin: RepoPin, patch: str) -> tuple[bool, str]`
  - `run_tests(pin: RepoPin, patches: list[str], test_files: list[str] | None = None, repeat: int = 1) -> TestRun`. `test_files=None` runs the existing suite (minus `FLAKY`); otherwise copies the files to `/work/_feature_tests/` and runs only those. With `repeat > 1`, a test is `passed` only if it passed every time.

- [ ] **Step 1: Write failing tests** (`@pytest.mark.docker`) using `fixtures/golden/` (Akshat's patches, Urja's graders):
  - `test_base_grader_fails`: `run_tests(PIN, [], ["fixtures/golden/graders/test_A.py"])` → every `test_new__*` id in `failed`.
  - `test_ref_grader_passes`: with `ref_A.patch` → `failed == {}`.
  - `test_bad_patch`: a garbage patch → all requested tests `"error"`, log mentions `git apply`.
  - `test_syntax_error_is_collection`: a test file with `def (` → kind `"collection"`.
  - `test_missing_api_kind`: a test calling `click.option(conflicts_with=...)` on base → kind `"missing_api"`.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** One `docker run --rm --network none` per call; `git apply` then `pytest --junitxml=/out/r.xml -p no:cacheprovider`. Classify from junit XML: `<error>` during collection → `"collection"`; failure message containing `AttributeError`, `ImportError`, `TypeError: ... unexpected keyword`, `NoSuchOption` → `"missing_api"`; `AssertionError` → `"assertion"`; else `"error"`. Logs to `runs/<pair_id or 'adhoc'>/logs/`.
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(sandbox): docker test runner with failure classification`.

### Task 5: `worker.py`: run one invocation against a patched click

**Files:** Create `factory/worker.py`, `docker/harness.py`, `tests/infra/test_worker.py`

**Interfaces:**
- Produces:
  - `class Worker` (context manager): `Worker(pin: RepoPin, patch: str | None, demo_app: str)`; `.call(inv: Invocation, timeout: float = 10.0) -> Outcome`; `.close()`
  - `fresh_call(pin: RepoPin, patch: str | None, demo_app: str, inv: Invocation) -> Outcome` (new container, used to confirm findings)

- [ ] **Step 1: Write failing tests** (`@pytest.mark.docker`) with the golden demo app and probe:
  - `test_probe_ref_a`: `Worker(PIN, ref_A, demo).call(probe).exit_code == 2`
  - `test_probe_ref_b`: same with `ref_B` → `exit_code == 0`
  - `test_fresh_matches_persistent`: `fresh_call(...) == Worker(...).call(...)` for the probe
  - `test_timeout`: demo app with `click.prompt` and no input → `Outcome(-1, ..., "Timeout")` within 12 s
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** `docker run -i` running `harness.py`, which reads JSON lines `{"argv","env","input"}`, runs `CliRunner(mix_stderr=False if supported).invoke(cli, ...)` and writes `{"exit_code","output","exception_type"}`. Recreate `cli` per call by re-executing `demo_app` (no state carried between calls).
- [ ] **Step 4: Run.** Expected: PASS.
- [ ] **Step 5: Commit** `feat(worker): persistent and fresh invocation runners`.

### Task 6: Basic gates G1–G4

**Files:** Modify `factory/gates_basic.py`; create `tests/infra/test_gates_basic.py`

**Interfaces:**
- Produces:
  - `g1_fail_before(pair: Pair, side: str) -> GateResult`: every `test_new__*` fails with kind in `{"assertion","missing_api"}`; every `test_preserved__*` passes; anything `"collection"`/`"error"` fails the gate.
  - `g2_pass_after(pair: Pair, side: str) -> GateResult`: grader + existing suite pass on the reference.
  - `g3_stability(pair: Pair, side: str, n: int = 5) -> GateResult`
  - `g4_public_api(grader_path: str) -> GateResult`: AST scan; fail on `from click._...`, `import click._...`, or attribute access on `click` whose name starts with `_`.
  - `parse_test_name(node_id: str) -> tuple[str, list[str]]` → `("new", ["R2","R4"])`

- [ ] **Step 1: Write failing tests** (no Docker; fake `TestRun` objects via monkeypatch of `sandbox.run_tests`):
  - `test_g1_collection_error_fails_gate`
  - `test_g1_preserved_must_pass_on_base`
  - `test_g4_rejects_private_import` (source `from click._compat import x`)
  - `test_parse_test_name` (`"tests/x.py::test_new__R2_R4__foo"` → `("new", ["R2","R4"])`)
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS. One Docker test: all four gates pass on the golden pair, side A.
- [ ] **Step 5: Commit** `feat(gates): G1-G4`.

### Task 7: `pipeline.py`: one pair end to end (target: 28 Nov)

**Files:** Create `factory/pipeline.py`, `tests/infra/test_pipeline.py`

**Interfaces:**
- Consumes (stubs land 25 Nov, real versions later):
  - Akshat: `discover_surface`, `propose_seed`, `novelty_gate`, `realism_gate`, `write_contracts`, `render_ticket`, `write_reference`, `repair_reference`
  - Urja: `derive_expectations`, `write_grader`, `repair_grader`, `g5_twin_separation`, `make_mutants`, `g6_mutants`, `g7_trace`
  - Heet: `make_heldout`, `valid_alternative`, `g6h_heldout`, `blind_solve`, `diagnose`
- Produces: `run_pair(family: str, pin: RepoPin, pair_id: str | None = None) -> Pair`; `evaluate_pair(pair_id: str, models: list[str]) -> Pair`
- Heet's `export_pair` and `replay` read the `runs/<pair_id>/` layout this task writes. Don't change that layout without telling Heet.

- [ ] **Step 1: Write failing test** `test_pipeline_order` with every consumed function monkeypatched to return golden fixtures: assert the stage order `surface → seed → G8 → G9 → contracts → tickets → heldout (Heet, ticket only) → references → expectations → graders (+ initial snapshot) → G1..G4 → G5 → mutants → G6 → G7 → G6h → accepted`, and that `runs/<id>/pair.json` exists after each stage.
- [ ] **Step 2: Write failing test** `test_repair_routing`: existing-suite failure in G2 → `repair_reference`; feature-test failure in G1/G2, G5 failure or G6 survivors → `repair_grader`; after 2 failed repairs → `status == "rejected"` with `reject_reason` naming the gate.
- [ ] **Step 3: Write failing test** `test_resume`: kill after `contracts`, re-run → no repeat calls to earlier stages.
- [ ] **Step 4: Implement.** Copy `graders/test_<side>.py` to `test_<side>.initial.py` before the first repair. Heet's held-out patches are generated **before** references are written (they only need the ticket), so independence is structural.
- [ ] **Step 5: Run, then commit** `feat(pipeline): end-to-end pair orchestration with repair and resume`.

### Task 8: CLI + README

**Files:** Create `factory/cli.py`, `factory/__main__.py`, `README.md`

**Interfaces:** Produces `python -m factory {generate,evaluate,export,report,replay}`:
- `generate --family F [--n N]`, `evaluate PAIR_ID --models m1,m2`, `export [--all]` (calls Heet's `export_pair`), `report` (calls Heet's `build_report`), `replay PACKAGE_DIR` (calls Heet's `replay`)

- [ ] **Step 1: Failing test** `test_cli_help` lists all five commands; `test_generate_calls_run_pair` (monkeypatched).
- [ ] **Step 2: Implement** with argparse (not click: avoids confusion with the click under test).
- [ ] **Step 3: README**: setup, env vars, one-command demo, architecture diagram from the design, reused open source list, limitations (copy from design §17).
- [ ] **Step 4: Commit** `feat(cli): factory command and README`.

### Task 9: Freeze & submit (4–6 Dec)
- [ ] Generate the final batch with the team; run `export --all` once Heet's export matches the final required template.
- [ ] Be the "second machine" for Heet's replay check: replay 3 random packages with `FACTORY_OFFLINE=1`.
- [ ] Tag `v1.0-submission`; submit.

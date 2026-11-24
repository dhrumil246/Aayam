# Heet: Independent Evaluation, Report & Demo Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `AGENTS.md` first. Edit only files listed under **Files** below.

**Goal:** Evidence the authors didn't design around: held-out wrong patches and valid alternatives (G6h), the blind solver, three-way diagnosis and the requirement-sensitivity experiment. Plus package export with offline replay, the static report, the Streamlit demo and the backup video.

**Architecture:** Packages `factory/evaluate/` and `factory/report/`, module `factory/export.py`, app in `demo/`. Your code **does not import** `factory.propose` (Akshat's references) or `factory.validate.grader` / `factory.validate.mutants`. It may import `factory.validate.search` and `factory.validate.expect` (they hold no reference knowledge). All model calls go through `factory.llm` with your own prompts in `prompts/evaluate/`.

**Tech Stack:** Python 3.12, `factory.llm`, `factory.sandbox`, `factory.worker`, Streamlit, plain HTML + inline CSS for the report.

**Spec:** `docs/design.md` (§8 G6h and three-way diagnosis, §10 sensitivity, §11 package layout, §12 demo script, §16 metrics).

## Global Constraints
- **Independence rule (AGENTS.md Rule 2):** never open `ref_*.patch`, `runs/*/patches/ref_*` or graders for a pair until your held-out patches for it are committed. The pipeline generates held-out patches **before** references exist.
- Held-out wrong patches and valid alternatives see **only** the ticket and the base repo.
- Held-out patches never feed `repair_grader`. They are measurement only.
- The blind solver sees **only** the ticket and the base repo: no `pair_id`, no twin, no hidden tests.
- Sensitivity results are reported as observations ("both patches produced the same outcome on the distinguishing case"), never as reasons ("the model ignored the sentence").
- Demo button label: **"Find a small difference"**.
- The report, the demo and `replay` must work with `FACTORY_OFFLINE=1` from saved files only.
- **`replay` never imports `factory.llm`.** It runs only on saved patches, tests, inputs and expected outcomes, so a missing cache entry can never turn a replay into a paid call. The Streamlit evidence screens and `python -m factory replay` call the **same** `export.replay` function; don't write a second runner in `demo/`.
- Export copies reference patches into packages. That's allowed by Rule 2 because export runs only on **accepted** pairs, whose held-out patches are already committed.

## Review Focus
1. A blind-solver patch that doesn't apply or crashes on import: verdict `"solver_failed_to_build"`, kept out of the three-way diagnosis counts.
2. A held-out "wrong" patch that the final grader accepts and the AI judge says is actually correct: record it as `"heldout_actually_valid"`, don't count it against the grader.
3. Demo input with shell quoting (`--name "a b"`): split with `shlex.split`, show the parsed argv to the viewer.
4. A pair where the solver failed on shared requirements: excluded from pivot scoring and listed separately in the sensitivity table.
5. The report opened with a pair still in `draft`: shown greyed with its current stage, not as accepted.

---

### Task 1: Golden held-out patches (24–25 Nov, before opening any reference)

**Files:** Create `fixtures/golden/heldout/wrong_A_1.patch`, `wrong_A_2.patch`, `wrong_A_3.patch`, `valid_alt_A.patch`, `valid_alt_B.patch`, `notes.md`

From `fixtures/golden/ticket_A.md` / `ticket_B.md` only:
- `wrong_A_1`: errors on the conflict but only when `--json` comes first (order bug).
- `wrong_A_2`: exits 2 without naming the options (violates "naming both").
- `wrong_A_3`: something you'd plausibly ship (your choice), documented in `notes.md`.
- `valid_alt_A` / `valid_alt_B`: correct by the ticket, but a different design from the obvious one (e.g. resolve conflicts in a `Context` callback instead of inside `Option`).

- [ ] **Step 1:** write them (your own LLM session is fine; give it only the ticket and click source). Check each applies in a local venv.
- [ ] **Step 2: Commit** `feat(golden): held-out patches written from tickets only`. **Only after this commit**, you may read the golden references.

### Task 2: Stubs (25 Nov)

**Files:** Create `factory/evaluate/{__init__,heldout,solver,diagnose,sensitivity}.py`, `factory/export.py`, `factory/report/{__init__,build}.py`

**Interfaces (Produces):**
- `heldout.make_heldout(ticket: str, pin: RepoPin, out_dir: Path, n_wrong: int = 3) -> list[Patch]` (`kind="heldout_wrong"`)
- `heldout.valid_alternative(ticket: str, pin: RepoPin, out: Path) -> Patch` (`kind="valid_alt"`)
- `heldout.g6h_heldout(pair: Pair, side: str, patches: list[Patch]) -> GateResult` (`gate="G6h"`, `detail = {"initial_accepted_wrong": int, "final_accepted_wrong": int, "valid_alt_passes": bool, "per_patch": {...}}`)
- `solver.blind_solve(ticket: str, pin: RepoPin, model: str, out: Path) -> Patch` (`kind="solver"`)
- `diagnose.diagnose(pair: Pair, side: str, solver_patch: Patch) -> dict`: keys `verdict` (`"pass" | "solver_mistake" | "grader_mistake" | "ambiguous_ticket" | "solver_failed_to_build"`), `finding`, `rationale`, `suggested_fix`
- `sensitivity.sensitivity(pairs: list[Pair], model: str) -> dict`
- `report.build.build_report(runs_dir: Path, out: Path) -> Path`
- `export.export_pair(pair: Pair, out_dir: Path) -> list[Path]`
- `export.replay(package_dir: Path) -> dict` (`{"matches": bool, "diffs": [...]}`)

Consumes: `sandbox.run_tests`, `worker.fresh_call`, `search.diff_search`, `expect.check`.

- [ ] **Step 1:** stubs raising `NotImplementedError`. **Commit** `chore(evaluate): stubs`.

### Task 3: Held-out generation + G6h

**Files:** `factory/evaluate/heldout.py`, `prompts/evaluate/{heldout_wrong,valid_alt}.md`, `tests/evaluate/test_heldout.py`

- [ ] **Step 1: Failing tests:**
  - `test_prompt_ticket_only` (fake llm): prompts contain the ticket; none contains `pair_id`, "twin", `test_new__`, or `+++ b/` from a reference
  - `test_g6h_counts` (fake sandbox): initial grader accepts 2 of 3 wrong patches, final accepts 0, valid alt passes → `detail == {"initial_accepted_wrong": 2, "final_accepted_wrong": 0, "valid_alt_passes": True, ...}`
  - `test_g6h_valid_alt_rejected_fails_gate`: final grader rejects the valid alternative → `passed False`, `detail["reason"]` mentions it
- [ ] **Step 2: Implement.** Use a **different model** from the reference writer where budget allows (`FACTORY_MODEL_HELDOUT`). G6h runs `sandbox.run_tests` with `graders/test_<side>.initial.py` and `test_<side>.py`.
- [ ] **Step 3: Commit** `feat(evaluate): held-out patches and G6h`.

### Task 4: Blind solver

**Files:** `factory/evaluate/solver.py`, `prompts/evaluate/solver.md`, `tests/evaluate/test_solver.py`

- [ ] **Step 1: Failing tests** (fake llm/sandbox): prompt hygiene as in Task 3; `apply_check` failure → one retry with the error; still failing → returns the patch with `model` set, and a later `diagnose` gives `"solver_failed_to_build"`.
- [ ] **Step 2: Implement** your own simple agent loop (don't import Akshat's): ticket + requested source files → diff → `apply_check` → existing suite → done. Max 3 iterations.
- [ ] **Step 3: Commit** `feat(evaluate): blind solver`.

### Task 5: Three-way diagnosis

**Files:** `factory/evaluate/diagnose.py`, `prompts/evaluate/judge.md`, `tests/evaluate/test_diagnose.py`

- [ ] **Step 1: Failing tests** (fake grader run, fake `diff_search`, fake judge):
  - solver passes grader → `"pass"`
  - judge says the ticket determines the output and the solver differs → `"solver_mistake"`
  - judge says the ticket allows the solver's output → `"grader_mistake"`, `suggested_fix` names the failing test
  - judge says undetermined → `"ambiguous_ticket"`, `suggested_fix` offers both "add clause: …" and "accept either outcome"
  - judge prompt contains the ticket, invocation and both outcomes, and **not** the grader source or reference patch
- [ ] **Step 2: Implement.** Grade the solver patch with `sandbox.run_tests`; on failure, `diff_search(pin, reference, solver_patch, demo_app, grammar)`; judge with `llm_json`.
- [ ] **Step 3: Commit** `feat(evaluate): three-way diagnosis`.

### Task 6: Requirement-sensitivity experiment

**Files:** `factory/evaluate/sensitivity.py`, `tests/evaluate/test_sensitivity.py`

- [ ] **Step 1: Failing tests** (fake solver outcomes):
  - patches A and B each pass own grader and fail the twin's → `"diagonal"`
  - both patches give the same probe outcome → `"same_outcome"`, plus which ticket's assertions it satisfies
  - a patch fails a shared-requirement test → pair goes to `"shared_fail"`, excluded from pivot rates
  - a patch passes both graders → `"both_pass"` (flag "investigate graders")
- [ ] **Step 2: Implement.** Separate blind runs per ticket. Step 1: shared-requirement tests only (test names not containing the pivot id). Step 2: probe via `worker.fresh_call` + `expect.check` against each ticket's expectations. Return per-pair labels and per-model rates: shared-pass, pivot-pass, same-outcome.
- [ ] **Step 3:** `@pytest.mark.llm @pytest.mark.docker` run on the golden pair with one model. **Commit** `feat(evaluate): requirement sensitivity`.

### Task 7: Export + offline replay (target 3 Dec)

**Files:** `factory/export.py`, `tests/evaluate/test_export.py`

**Interfaces:**
- Consumes: the `runs/<pair_id>/` layout from Dhrumil's pipeline (AGENTS.md), `sandbox.run_tests`, `worker.fresh_call`, `expect.check`.
- Produces: `export_pair(pair: Pair, out_dir: Path) -> list[Path]` (layout = `docs/design.md` §11); `replay(package_dir: Path) -> dict`. Dhrumil's CLI calls both.

- [ ] **Step 1: Failing test** `test_export_layout`: export the golden pair; assert `task.md` is the only file outside `env/` and `evaluator/`, and it contains no `pair_id`, no "twin" and no other side's pivot text. `evaluator/meta.json` has `pair_id`, `twin_package`, `pivot_clause`.
- [ ] **Step 2: Failing test** `test_export_bundles_patches`: `evaluator/patches/` contains every mutant, held-out and solver patch recorded for the pair, and `replay.sh` is executable.
- [ ] **Step 3: Failing test** `test_replay_offline` (`@pytest.mark.docker`): with `FACTORY_API_KEY` unset, `FACTORY_OFFLINE=1` and `runs/llm_cache` deleted, `replay(pkg)["matches"] is True`. Changing one stored outcome in `evidence/probe.json` makes it `False` with a diff naming that file.
- [ ] **Step 3b: Failing test** `test_replay_never_imports_llm`: run `replay` in a subprocess after `sys.modules["factory.llm"] = None` (any import of it then raises `ImportError`); it still returns `matches: True`.
- [ ] **Step 4: Implement.** `env/Dockerfile` pins the base image digest and installs from `requirements.lock`. `replay.sh` = `FACTORY_OFFLINE=1 python -m factory replay "$(dirname "$0")"`. `replay` re-runs, from saved files only: the basic matrix (G1–G3), the probe, every mutant, held-out and solver patch, then compares against `evidence/`.
- [ ] **Step 5: Run, then commit** `feat(export): packages and offline replay`.
- [ ] **Step 6 (4 Dec):** when the required package template is final, adapt `export_pair` only. Then the 5 Dec replay check: Dhrumil replays 3 random packages on their machine with `FACTORY_OFFLINE=1`; save the output to `report/replay_check.txt`.

### Task 8: Static report (target 4 Dec)

**Files:** `factory/report/build.py`, `factory/report/template.html`, `tests/evaluate/test_report.py`

- [ ] **Step 1: Failing test** `test_report_offline`: build from a `runs/` dir containing only the golden pair JSON → HTML contains the basic matrix, the G6h counts, the probe outcomes, family coverage, and cost per package; no `<script src=` to any external host.
- [ ] **Step 2: Implement** sections in design §16 order. **Headline first:** held-out wrong patches accepted by initial vs final graders. Cross-grade separation is shown as a gate, not a result. Draft and rejected pairs are listed with their stage and reason.
- [ ] **Step 3: Commit** `feat(report): static evidence report`.

### Task 9: Demo app + video (4–5 Dec)

**Files:** `demo/app.py`, `demo/run_demo.sh`, `demo/script.md`

Follow design §12 in order. Screens:
1. Pick a pair → the two tickets with the differing sentence highlighted (`difflib`).
2. Basic validation matrix from saved evidence.
3. Pivot probe: show the invocation, ask the audience to predict, then reveal both outcomes (live `worker.fresh_call`).
4. M1 before/after (from `docs/m1.md` and saved runs).
5. Break the grader: text input → `shlex.split` → both workers side by side → **"Find a small difference"** → `diff_search` → show the small case → export as a pytest file → run it with `sandbox.run_tests` and show the result.
6. Diagnosis examples (one of each verdict where available) and the numbers.

- [ ] **Step 1:** build screens 1–3 against the golden pair; works with `FACTORY_OFFLINE=1`.
- [ ] **Step 2:** screens 4–6.
- [ ] **Step 3:** `run_demo.sh` = `streamlit run demo/app.py`. Rehearse twice with the team; record the full run as the backup video.
- [ ] **Step 4: Commit** `feat(demo): break-the-grader demo app`.

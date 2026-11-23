# Urja: Graders, Search & Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `AGENTS.md` first. Edit only files listed under **Files** below.

**Goal:** Everything about tests: ticket-derived expectations, graders, the pivot probe gate (G5), differential search with shrinking, finding classification, mutants (G6) and traceability (G7). You also drive **Milestone M1** (1 Dec).

**Architecture:** Package `factory/validate/`. **Expected outcomes always come from a ticket, never from a reference's output.** Differential search is a lead finder; its results become tests only after expectations are written from the tickets. All code execution goes through `factory.sandbox` / `factory.worker`.

**Tech Stack:** Python 3.12, Hypothesis (`find`, strategies), `ast`, `factory.llm`, `factory.sandbox`, `factory.worker`.

**Spec:** `docs/design.md` (§8 G5–G7 and "Pivot probe and differential search").

## Global Constraints
- Graders follow the AGENTS.md naming convention: `test_new__R<n>__...` / `test_preserved__R<n>__...`, one self-contained file with the demo app at the top.
- Graders use only the public click API and `click.testing.CliRunner`.
- `derive_expectations` sees **only** one ticket and the probe. `write_grader` sees the contract and ticket, **never** a reference patch.
- `Assertion.python` uses only: the name `outcome`; attributes `exit_code`, `output`, `exception_type`; literals; comparisons; `in`/`not in`; `and`/`or`/`not`; `len()`; and the str methods `lower`, `count`, `find`, `strip`, `splitlines`.
- Hypothesis shrinking gives a **small**, not guaranteed shortest, example. Say "small" everywhere.
- Budget exhausted with no pivot finding → record `"no distinguishing case found within budget"`.

## Review Focus
1. Outputs that differ only in trailing whitespace or newline: normalise (`rstrip` each line) before comparing, or the search reports noise.
2. An assertion that's a tautology (`outcome.exit_code == outcome.exit_code`) or ignores `outcome`: reject in `validate_assertion`.
3. A pivot assertion that both references satisfy: G5 must fail (the probe doesn't separate them), not pass.
4. A Hypothesis-found case that doesn't reproduce in `fresh_call`: drop it, count it in `detail["not_reproduced"]`.
5. A grader whose `test_new__` test passes on base because it only checks exit code 0: G1 (Dhrumil) catches it, and `repair_grader` must receive that failure text.

---

### Task 1: Golden graders by hand (24–25 Nov)

**Files:** Create `fixtures/golden/graders/test_A.py`, `test_B.py`, `test_A_weak.py`

Uses Akshat's golden contracts (conflict feature; see `docs/agents/akshat.md` Task 1).
- `test_A.py`: preserved tests for R1–R3 (single flag works, unrelated option unaffected); new tests for R1 (parameter accepted), R4 (`--json --yaml` → exit 2, output mentions both flags; also reversed order).
- `test_B.py`: same preserved tests; R4: `--json --yaml` → exit 0, `fmt=yaml`; `--yaml --json` → `fmt=json`.
- `test_A_weak.py`: the **initial grader for M1**. It's realistic but misses the reversed-order case and only checks `exit_code != 0` (no flag names). It must still pass G1/G2 on the golden pair.

- [ ] **Step 1:** write the three files; check in a local venv with Akshat's patches (base fails all `test_new__`; refs pass their own grader).
- [ ] **Step 2: Commit** `feat(golden): graders and weak M1 grader`.

### Task 2: Stubs (25 Nov)

**Files:** Create `factory/validate/{__init__,expect,grader,probe,search,mutants,trace}.py`

**Interfaces (Produces):**
- `expect.derive_expectations(ticket: str, probe: Invocation, requirement_id: str) -> list[Assertion]`
- `expect.validate_assertion(a: Assertion) -> list[str]`
- `expect.check(assertions: list[Assertion], outcome: Outcome) -> list[tuple[Assertion, bool]]`
- `grader.write_grader(contract: Contract, ticket: str, assertions: list[Assertion], out: Path) -> str`
- `grader.check_grader_names(path: str, contract: Contract) -> list[str]`
- `grader.repair_grader(contract: Contract, ticket: str, grader_path: str, failure: str, findings: list[Finding]) -> str`
- `grader.probe_test_source(assertions: list[Assertion], probe: Invocation, requirement_id: str) -> str`
- `probe.g5_twin_separation(pair: Pair) -> GateResult` (`gate="G5"`)
- `search.invocations(grammar: dict) -> hypothesis.strategies.SearchStrategy[Invocation]`
- `search.diff_search(pin: RepoPin, patch_a: str | None, patch_b: str | None, demo_app: str, grammar: dict, budget: int = 200) -> list[Finding]`
- `search.classify_finding(finding: Finding, ticket_a: str, ticket_b: str) -> FindingLabel`
- `mutants.make_mutants(contract: Contract, ticket: str, reference: Patch, out_dir: Path) -> list[Patch]`
- `mutants.g6_mutants(pair: Pair, side: str, mutants: list[Patch]) -> GateResult` (`gate="G6"`, `detail["killed"]: {mutant_path: [test ids]}`, `detail["survivors"]`)
- `trace.g7_trace(pair: Pair, side: str, g6: GateResult) -> GateResult` (`gate="G7"`)

`diff_search` is also used by Heet (solver vs reference), so `patch_b` can be any patch.

- [ ] **Step 1:** stubs raising `NotImplementedError`. **Commit** `chore(validate): stubs`.

### Task 3: Expectations (no Docker)

**Files:** `factory/validate/expect.py`, `prompts/validate/expect.md`, `tests/validate/test_expect.py`

- [ ] **Step 1: Failing tests:**
  - `test_check_golden_a`: assertions `["outcome.exit_code == 2", "'--json' in outcome.output and '--yaml' in outcome.output"]` → both True on `Outcome(2, "Error: --json conflicts with --yaml")`, False on `Outcome(0, "fmt=yaml")`
  - `test_validate_rejects_dunder`: `"outcome.__class__"` → error
  - `test_validate_rejects_call`: `"__import__('os')"` → error
  - `test_validate_rejects_tautology`: `"1 == 1"` (no `outcome`) → error
  - `test_derive_sees_only_ticket` (fake llm): the prompt contains ticket A text and the probe argv, and none of: `pair_id`, ticket B pivot text, "patch", "diff"
- [ ] **Step 2: Implement.** `validate_assertion` walks the `ast` against the allow-list in Global Constraints. `check` evaluates with `eval(compile(...), {"__builtins__": {"len": len}}, {"outcome": outcome})` only after validation passes. The prompt tells the model to assert only what the ticket determines and leave open items unasserted.
- [ ] **Step 3: Commit** `feat(validate): ticket-derived expectations`.

### Task 4: Graders

**Files:** `factory/validate/grader.py`, `prompts/validate/{grader,repair_grader}.md`, `tests/validate/test_grader.py`

- [ ] **Step 1: Failing tests:**
  - `test_names_golden_ok`: `check_grader_names("fixtures/golden/graders/test_A.py", golden_A) == []`
  - `test_names_unknown_requirement`: `test_new__R9__x` → error naming R9
  - `test_names_every_requirement_covered`: removing all R3 tests → error naming R3
  - `test_probe_test_source`: output compiles, defines `test_new__R4__pivot_probe`, invokes the probe argv and asserts each assertion
  - `test_write_grader_prompt_has_no_reference` (fake llm): prompt lacks `+++ b/` and "patch"
- [ ] **Step 2: Implement.** `write_grader`: model writes tests from contract + ticket → append `probe_test_source(...)` → `check_grader_names` → up to 2 retries. `repair_grader` gets the failing gate's text plus findings labelled `pivot`, each turned into a new test whose expectations come from `derive_expectations` on that finding's invocation, never the reference output.
- [ ] **Step 3:** `@pytest.mark.llm @pytest.mark.docker`: generate graders for the golden contracts; G1–G4 pass (Dhrumil's gates). Paste.
- [ ] **Step 4: Commit** `feat(validate): grader generation and repair`.

### Task 5: Pivot probe gate (G5)

**Files:** `factory/validate/probe.py`, `tests/validate/test_probe.py`

- [ ] **Step 1: Failing tests** (fake worker and sandbox):
  - `test_g5_golden_passes`: probe outcomes A=`(2, "...--json...--yaml")`, B=`(0, "fmt=yaml")` → passed
  - `test_g5_same_behaviour_fails`: both outcomes `(2, ...)` → failed, `detail["reason"] == "probe does not separate twins"`
  - `test_g5_cross_grade`: ref A vs grader B must fail on a `test_new__R4__` test and vice versa; if ref A passes grader B → failed
- [ ] **Step 2: Implement.** `worker.fresh_call` for each reference on `contract.probe`; `expect.check` own and twin pivot assertions; then `sandbox.run_tests` cross-grade. Store outcomes in `detail`.
- [ ] **Step 3: Commit** `feat(validate): G5 pivot probe and cross-grade`.

### Task 6: Differential search + classification

**Files:** `factory/validate/search.py`, `prompts/validate/classify.md`, `tests/validate/test_search.py`

- [ ] **Step 1: Failing tests** (fake worker = two pure Python functions, no Docker):
  - `test_strategy_respects_grammar`: 200 draws, every argv token is in the grammar, `len(argv) <= max_tokens`
  - `test_finds_and_shrinks`: fake A errors when both `--json` and `--yaml` appear; fake B never errors; with extra noise options in the grammar → the finding's argv has length 2
  - `test_normalises_whitespace`: outputs differing only in trailing spaces → no finding
  - `test_budget_exhausted`: identical fakes → `[]`
  - `test_not_reproduced_dropped`: fresh replay returns a different outcome → finding dropped
- [ ] **Step 2: Implement.**
  - `invocations(grammar)`: `st.lists(st.sampled_from(tokens), max_size=max_tokens)` where value options expand to `[flag, value]`; env from `st.dictionaries` over the grammar keys; stdin from `st.sampled_from`.
  - `diff_search`: open one `Worker` per side; `hypothesis.find(invocations(grammar), disagrees, settings=settings(max_examples=budget, database=None, deadline=None))` (catch `NoSuchExample` → `[]`). Confirm with `worker.fresh_call` on both sides → `replayed_fresh=True`.
  - `classify_finding`: `llm_json` sees both tickets, the invocation and both outcomes; returns `pivot` / `shared` / `open`.
- [ ] **Step 3:** `@pytest.mark.docker`: golden refs → one finding, argv length ≤ 3, label `pivot`.
- [ ] **Step 4: Commit** `feat(validate): differential search with shrinking`.

### Task 7: Mutants (G6) + traceability (G7)

**Files:** `factory/validate/mutants.py`, `factory/validate/trace.py`, `prompts/validate/mutant.md`, `tests/validate/test_mutants.py`

- [ ] **Step 1: Failing tests:**
  - `test_one_mutant_per_requirement` (fake llm): golden contract with 4 requirements → 4 patches, each `requirement_id` set
  - `test_g6_survivor_reported` (fake sandbox): one mutant passes the grader → `passed False`, its path in `detail["survivors"]`
  - `test_g7_requirement_without_test`: g6 kills cover R1–R3 only and no test names R4 → G7 fails naming R4
- [ ] **Step 2: Implement.** The mutant prompt gets the ticket, the reference patch and one requirement: "write the most plausible implementation that a careful developer might ship, which violates only this requirement". `g6_mutants` runs the grader per mutant via `sandbox.run_tests`. `g7_trace` maps tests (from names) and killed mutants (from `requirement_id`) to requirements.
- [ ] **Step 3: Commit** `feat(validate): mutant gauntlet and traceability`.

### Task 8: Milestone M1 (by 1 Dec, with Heet)

**Files:** Create `tests/validate/test_m1.py` (`@pytest.mark.docker`), `runs/m1/` (output, not committed; copy the summary to `docs/m1.md`)

- [ ] **Step 1:** using the golden pair, grader `test_A_weak.py` as the initial grader, and Heet's held-out wrong patch for A (`fixtures/golden/heldout/`): assert the weak grader **accepts** the wrong patch.
- [ ] **Step 2:** run `diff_search(ref_A, wrong_patch)` → finding → `derive_expectations` on ticket A → `repair_grader` → new grader.
- [ ] **Step 3:** assert the new grader **rejects** the wrong patch and **accepts** Heet's valid alternative for A.
- [ ] **Step 4:** save both runs (before/after) and write `docs/m1.md` (what was missed, the small case found, the new test). **Commit** `test(m1): before/after grader improvement`. Post in chat; this is the demo's core evidence.

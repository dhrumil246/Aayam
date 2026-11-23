# Akshat: Features, Contracts & References Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Read `AGENTS.md` first. Edit only files listed under **Files** below.

**Goal:** Turn click into realistic, novel twin feature ideas; write frozen contracts and public tickets; write reference patches from the tickets.

**Architecture:** Package `factory/propose/`. Every model call goes through `factory.llm`; prompts live in `prompts/propose/`. Every generated patch is checked through `factory.sandbox`. You never write graders, so references can't be written to pass a specific test.

**Tech Stack:** Python 3.12, `factory.llm`, `factory.sandbox`, `factory.worker`, `git`, `gh` (optional, for PR/issue titles).

**Spec:** `docs/design.md` (§6 concepts, §7 stages 1–4, §8 G8–G9, §9 families).

## Global Constraints
- Each contract has **exactly one** requirement with `pivot=True`. Shared requirements are **text-identical** between A and B; only the pivot text differs.
- `demo_app` is identical for A and B, compiles, and defines `cli`.
- `probe` must be drawable from `grammar` (every token in it appears in the grammar).
- Tickets never contain `pair_id`, the word "twin", or the other side's pivot text.
- Families: `conflict, precedence, repetition, validation, lifecycle, deprecation, retry` (AGENTS.md).
- Novelty is checked against click **main**, docs, CHANGES and open PR/issue titles, not just the pinned tag.

## Review Focus
1. A seed whose "new" option already exists under another name (e.g. a third-party pattern click later adopted): G8 must search synonyms the model suggests, not only the literal name.
2. A contract where the pivot is only visible in error wording (both policies error, one says "cannot" and one says "conflicts"): reject in `validate_contracts` because wording is an open item, not a rule.
3. Ticket rendering when `open_items` is empty: still prints the "Left to you" section saying nothing is left open.
4. A reference patch that touches test files in click's own `tests/`: reject, references change library code only.
5. A demo app that relies on terminal colour or width: reject; outcomes must be plain text.

---

### Task 1: Golden pair by hand (24–25 Nov, everyone depends on it)

**Files:** Create `fixtures/golden/seed.json`, `contract_A.json`, `contract_B.json`, `ticket_A.md`, `ticket_B.md`, `demo_app.py`, `ref_A.patch`, `ref_B.patch`

The default golden feature (change it only if novelty fails and tell the team the same day):
- **Family:** `conflict`. **Feature:** a new `conflicts_with` parameter on `click.Option`: a list of other option names that may not be combined with it.
- **Policy A:** combining conflicting options is a usage error (exit 2) naming both options. *Reason:* scripts fail loudly instead of guessing.
- **Policy B:** when conflicting options are combined, the one that appears **last** on the command line wins, with no error. *Reason:* lets users override an alias or default in shell wrappers.
- **Shared requirements:** R1 `conflicts_with` is accepted by `click.option`/`click.Option`; R2 one of the options alone behaves exactly as today; R3 options not listed are unaffected; R4 is the pivot (A or B text above).
- **Demo app:** `--json` and `--yaml` flags (`flag_value` into one `fmt` param), each `conflicts_with` the other; prints `fmt=<value>`.
- **Probe:** `["--json", "--yaml"]`. A → exit 2, output mentions both `--json` and `--yaml`. B → exit 0, prints `fmt=yaml`.
- **Open items:** exact error wording; whether `--help` mentions the conflict.

- [ ] **Step 1: Novelty check:** grep click main for `conflict`, `mutually`, `exclusive` in `src/` and `docs/`, and search issues/PRs. Record results in `fixtures/golden/novelty.txt`.
- [ ] **Step 2: Write** `seed.json`, both contracts (valid `schema.Contract` JSON, loadable with `schema.load`), `demo_app.py` and both tickets (via Task 5's template once it exists; by hand today).
- [ ] **Step 3: Write** `ref_A.patch` and `ref_B.patch` against the pin (an LLM can draft; you review). Check locally in a venv: patch applies, click's own `pytest tests/` passes, demo app gives the probe outcomes above.
- [ ] **Step 4: Commit** `feat(golden): hand-made conflict twin pair`, and post in chat. **Heet must not open the `ref_*.patch` files**.

### Task 2: Stubs (25 Nov)

**Files:** Create `factory/propose/{__init__,surface,seeds,novelty,realism,contract,ticket,reference}.py`

**Interfaces (Produces, used by Dhrumil's pipeline):**
- `surface.discover_surface(pin: RepoPin) -> str`
- `seeds.propose_seed(surface: str, family: str, avoid: list[str]) -> Seed`
- `novelty.novelty_gate(seed: Seed) -> GateResult` (`gate="G8"`)
- `realism.realism_gate(seed: Seed, surface: str) -> GateResult` (`gate="G9"`)
- `contract.write_contracts(seed: Seed, surface: str) -> tuple[Contract, Contract]`
- `contract.validate_contracts(a: Contract, b: Contract) -> list[str]` (empty = valid)
- `ticket.render_ticket(contract: Contract, seed: Seed) -> str`
- `reference.write_reference(contract: Contract, ticket: str, pin: RepoPin, out: Path) -> Patch`
- `reference.repair_reference(contract: Contract, ticket: str, pin: RepoPin, patch: Patch, failure: str) -> Patch`

- [ ] **Step 1:** each function raises `NotImplementedError`; signatures exactly as above. **Commit** `chore(propose): stubs`.

### Task 3: `validate_contracts` + `render_ticket` (no model calls)

**Files:** `factory/propose/contract.py`, `factory/propose/ticket.py`, `tests/propose/test_contract_rules.py`, `tests/propose/test_ticket.py`

- [ ] **Step 1: Failing tests:**
  - `test_golden_contracts_valid`: `validate_contracts(golden_A, golden_B) == []`
  - `test_two_pivots_rejected`, `test_shared_text_mismatch_rejected`, `test_demo_app_mismatch_rejected`, `test_probe_not_in_grammar_rejected`, `test_demo_app_without_cli_rejected` (each mutates the golden contract and asserts one error message)
  - `test_ticket_hides_twin`: rendered ticket A has no `pair_id`, no "twin", no B pivot text
  - `test_ticket_open_items_section`: contains a "Left to you" heading listing each open item; with none, says so
  - `test_ticket_golden_snapshot`: equals `fixtures/golden/ticket_A.md`
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** `demo_app` check: `compile()` it and confirm a top-level `cli` assignment or def via `ast`. The ticket template (fixed text, no LLM): title, background (seed.feature + this side's policy reason), numbered requirements, public API, "Left to you", "How it will be checked" (public API and the command behaviour only; no hidden-test details).
- [ ] **Step 4: Run.** Expected: PASS. **Commit** `feat(propose): contract rules and ticket template`.

### Task 4: Surface map + seed proposal

**Files:** `factory/propose/surface.py`, `factory/propose/seeds.py`, `prompts/propose/surface.md`, `prompts/propose/seed.md`, `tests/propose/test_seeds.py`

- [ ] **Step 1: Failing tests** (fake `llm` via monkeypatch):
  - `test_surface_lists_public_names`: output includes every name in click's `__init__.py` import list (parsed by `ast`, not the model)
  - `test_surface_cached`: second call with same sha does no model call (`runs/surface_<sha>.md`)
  - `test_seed_has_family_and_reasons`: returned `Seed.family == "precedence"`, `reason_a`, `reason_b` non-empty
  - `test_seed_avoids`: `avoid=["conflicts_with"]` appears in the prompt
- [ ] **Step 2: Implement.** The surface map = public names (algorithm) + a model summary of extension points (`Option`, `Parameter`, `Context`, parameter sources, chained groups, prompts). The seed prompt gives the family definition from design §9 and requires: one feature, one policy dimension, two realistic policies with stakeholder reasons, and a pivot visible through command behaviour (exit code, which value wins, which values are reported), **not** wording.
- [ ] **Step 3:** one `@pytest.mark.llm` run per family; paste the 7 seeds in the PR.
- [ ] **Step 4: Commit** `feat(propose): surface map and seed proposals`.

### Task 5: Novelty (G8) + realism (G9)

**Files:** `factory/propose/novelty.py`, `factory/propose/realism.py`, `prompts/propose/{novelty,realism}.md`, `tests/propose/test_gates.py`

- [ ] **Step 1: Failing tests:**
  - `test_novelty_rejects_existing`: a seed for `envvar` support (already in click) → `passed is False`, `detail["matches"]` non-empty
  - `test_novelty_uses_synonyms`: model-suggested synonyms are all grepped (fake llm returns `["exclusive","mutually"]`; assert both searched)
  - `test_realism_threshold`: fake scores `{fit:5, reason:4, usefulness:3}` → mean 4.0 → pass; mean 3.67 → fail
- [ ] **Step 2: Implement.** G8: model suggests 5 search terms → grep `src/`, `docs/`, `CHANGES.rst` on a clone of **main** (`runs/repos/main/`, refreshed daily) + titles from `gh search issues/prs --repo pallets/click` (cached to `runs/gh_titles.json`; offline uses cache) → model judges matches. G9: rubric 1–5 on fit-with-click-design, stakeholder reason, usefulness; pass at mean ≥ 4; `detail["needs_human_signoff"] = True` always.
- [ ] **Step 3: Commit** `feat(propose): G8 novelty and G9 realism gates`.

### Task 6: `write_contracts`

**Files:** `factory/propose/contract.py`, `prompts/propose/contract.md`, `tests/propose/test_write_contracts.py`

- [ ] **Step 1: Failing tests:** fake llm returning the golden contract JSON → `write_contracts` returns two `Contract`s equal to golden; fake returning two pivots → one retry with the validation errors in the prompt, then raises `ValueError`.
- [ ] **Step 2: Implement:** one `llm_json` call producing both contracts together (so shared text matches), then `validate_contracts`; up to 2 retries with errors fed back.
- [ ] **Step 3:** `@pytest.mark.llm` run on 3 seeds from Task 4; all three pass validation.
- [ ] **Step 4: Commit** `feat(propose): contract generation`.

### Task 7: `write_reference` + `repair_reference`

**Files:** `factory/propose/reference.py`, `prompts/propose/{reference,repair_reference}.md`, `tests/propose/test_reference.py`

- [ ] **Step 1: Failing tests** (fake llm + fake sandbox):
  - `test_rejects_patch_touching_tests`: diff with `tests/` paths → retried, never returned
  - `test_iterates_on_apply_failure`: first diff fails `apply_check`, second succeeds → returns second, prompt 2 contains the apply error
  - `test_smoke_probe_no_crash`: reference whose probe outcome has `exception_type` other than `SystemExit`/`None` → retried
- [ ] **Step 2: Implement:** the model sees the ticket + the click source files it asks for (one round of "which files do you need?") → unified diff → `apply_check` → `sandbox.run_tests(pin, [patch])` (existing suite) → `worker.fresh_call` on the probe must not raise an unexpected exception. Max 3 iterations. Write to `out`, return `Patch(kind="reference", side=contract.side)`. **Never read or receive grader files.**
- [ ] **Step 3:** `@pytest.mark.docker @pytest.mark.llm`: regenerate references for the golden contracts; both pass Urja's golden graders (via `sandbox.run_tests`). Paste results.
- [ ] **Step 4: Commit** `feat(propose): reference patch agent loop`.

### Task 8: Final batch (2–4 Dec)
- [ ] Run `python -m factory generate --family <f>` for all 7 families until ≥8 accepted pairs cover ≥5 families.
- [ ] Human sign-off: read each accepted pair's tickets; record yes/no + one line in `runs/<id>/signoff.txt`. Reject anything nobody would want.
- [ ] Send Heet the 2 best pairs for the demo.

# Twin-Ticket Task Factory — Design

Design as of 2026-11-23 · deadline 2026-12-06

## 1. Intent

Build a **reusable factory that turns a real repository into new, runnable feature-development tasks**, and prove the tasks are good.

The one original idea that makes the factory better than a generic "LLM writes a spec, code and tests" pipeline:

> Generate tasks in **twins**: two standalone tickets from the same commit that share a feature and differ in **one meaningful rule**. The factory then **searches the real code for the shortest input where the two rules give different results**, and makes sure each ticket's grader checks it.

That one mechanism supplies evidence for three scored criteria at once:

- **Validity:** the tests demonstrably reject a plausible wrong implementation (the twin).
- **Variation:** the difference is behavioural, proven by execution, not wording.
- **Impact:** twins measure whether an AI solver actually reads the requirement (*requirement sensitivity*).

**Pitch line:** "Our factory generated two individually solvable tasks and found the test needed to tell them apart."

## 2. Evaluation criteria we target

| Weight | Criterion | What's expected | How we answer it |
|---|---|---|---|
| 25% | Working, repeatable implementation | Start from one supplied repo; generate multiple tasks; approach should carry over when the repo changes. Teams choose **one** of the three repos. | End-to-end CLI on click; many features from different behaviour families; repo specifics confined to one adapter file. |
| 25% | Validation | Show: original repo passes existing tests, feature test fails on original, reference passes both. | The basic validation matrix (G1–G3) is in every package and shown **first** in the demo. Extra gates follow. |
| 20% | Variation | "Black Friday banner → Christmas banner" is *not* variation. Explain how the generator produces variation. | Behaviour-family catalogue + twin rule pairs + cross-grading proof (section 8). |
| 15% | Originality | Originality lives in the **checks you design during generation**. AI may write the reference; show evidence it meets the requirement. | Differential search + shrinking, mutant gauntlet, blind solver, three-way diagnosis. |
| 15% | Impact & communication | Value for evaluating AI coders; clear demo. | Requirement-sensitivity experiment; "break the grader" live demo; replayable evidence. |

Expected package contents: starting repo + version recorded, instructions in **Markdown**, solution as a **patch**, tests. **The exact template was not final**, so export is a thin, last, swappable stage.

## 3. Goals, non-goals, anti-goals

**Goals**
- One command generates and validates a task pair from a pinned click commit.
- Every package ships with the basic validation matrix and passes it.
- 8–12 validated pairs (16–24 standalone packages) across at least 5 behaviour families.
- An evidence report a reviewer can open locally without any API key.
- A live demo: generate → validate → cross-grade → "break the grader".

**Non-goals**
- Supporting all three repos. (One repo; a second is a bonus only if everything else is green by 3 Dec.)
- A polished web app. A CLI plus a small demo page is enough.
- Training data at scale. Fewer, proven tasks beat many.
- Adaptive follow-up generation for the first deadline. It's a later stretch goal.

**Anti-goals** (would be failure even if it "works")
- Tasks that differ only in names, wording or literal values.
- Tests that import private internals, so only the reference design passes.
- Tickets with behaviour the spec never states but the tests check ("wide" tests).
- Features that already exist upstream (contaminated, not new).
- Testable features no real user would want.
- Evidence that only reproduces with paid API calls.

## 4. Constraints

- 13 days (24 Nov – 6 Dec), up to 4 people, standard laptops.
- Model access: provided model credits (provider TBC). All model calls go through **one** function so the provider is a config value.
- No API keys in the repo. Reused open source must be listed in the README.
- Native stack: tasks run in click's own Python + pytest setup.

## 5. Approaches considered

| Approach | Trade-off | Verdict |
|---|---|---|
| **A. Reverse SWE-smith:** delete an existing feature, ask for it back | Cheap; existing tests give validity. But not new, likely in training data, weak originality. | Rejected |
| **B. Mine upstream feature PRs** (FEA-Bench / SWE-Dev style) | Realistic, but contaminated, not "generation", copies prior work. | Rejected |
| **C. Novel feature synthesis + adversarial validation gauntlet** (our first idea) | Original, strong on validity. On its own, variation is asserted rather than proven. | Merged |
| **D. Twin tickets + shortest-difference search + break-the-grader demo** (team idea) | Proves variation and requirement sensitivity, great demo. Original "behaviour model" component was a big scope risk; references can share a bug. | Merged |
| **Chosen: C + D.** Twins are the product, differential search is the engineering centrepiece, the gauntlet is the proof, break-the-grader is the demo. | Twice the generation cost per feature; more gates to build. | **Chosen** |

Changes made while merging:
- **No hand-built behaviour model.** Differential search runs directly on the **two real patched copies of click**, so every counterexample is real-repo evidence from the start.
- **The mutant gauntlet is mandatory**, because two LLM references can share the same bug and cross-grading would stay green.
- **Breadth across behaviour families is mandatory**, so twins don't all look like one template.

**Repo choice: `pallets/click`.** Python gives the best tooling (pytest, Hypothesis, mutmut) and the most reliable LLM patches. A CLI invocation is naturally a sequence of actions, so break-the-grader maps cleanly. zod is a fallback; jsoncpp is avoided (slow builds, poor mutation tooling).

## 6. Core concepts

- **Seed feature:** one repo-grounded feature idea tied to an existing extension point (e.g. option declaration, parameter source resolution, chained command results).
- **Policy dimension:** the one decision inside the feature where two reasonable rules exist. Each rule has a **stakeholder reason** (why a real team would pick it).
- **Contract:** numbered, testable requirements R1…Rn. Shared clauses are identical across twins; exactly one clause (the *pivot clause*) differs. The contract also lists **what is intentionally left open**.
- **Ticket:** the public brief (Markdown) a solver sees. It is derived from the contract and never includes hidden tests or the twin.
- **Grader:** the hidden feature tests for one ticket. Each test cites the requirement(s) it checks.
- **Package:** one standalone task = ticket + base commit + reference patch + grader + evidence. Twins are two packages plus a `pair.json` linking them.

## 7. Pipeline

```
          ┌──────────── adapter (click) ────────────┐
 [0] Pin & baseline ─▶ [1] Discover surfaces ─▶ [2] Propose seeds + policy pairs
                                                     │  (novelty + realism checks)
                                                     ▼
 [3] Freeze contracts A/B ─▶ [4] Reference patches A/B ─▶ [5] Graders A/B (from contract only)
                                                     │
                                                     ▼
 [6] Validation gauntlet  G1…G9  ──fail──▶ repair loop (max 2) ──▶ reject + log reason
                                                     │ pass
                                                     ▼
 [7] Blind solver + diagnosis ─▶ [8] Export packages + pair.json + evidence ─▶ [9] Report
```

| Stage | What it does | AI or algorithm |
|---|---|---|
| 0 Pin & baseline | Clone click at a tag, record commit SHA, build a Docker image, run the full suite, record any pre-existing flaky or failing tests. | Algorithm |
| 1 Discover surfaces | Summarise public API and extension points (decorators, `Option`/`Parameter`, `Context`, parameter sources, `CliRunner`). Output a short "surface map". | AI reads code; static listing of public names by algorithm |
| 2 Propose | From the surface map and a target behaviour family, propose a seed feature and policy pair with stakeholder reasons. Reject if it already exists (grep current source, docs, CHANGES) or scores low on a realism rubric. | AI proposes; algorithm checks novelty |
| 3 Contracts | Write shared clauses, the pivot clause for A and B, the open items and the public API signature. Freeze them (hash stored). | AI, then frozen |
| 4 References | Agent loop in the sandbox implements contract A, then B, each from base. | AI |
| 5 Graders | Tests generated **from the contract only**, never shown the reference patch. Public API only. Each test tagged with requirement IDs. | AI |
| 6 Gauntlet | Gates below. Failed gates trigger at most 2 repair attempts (regenerate tests or patch), then the pair is rejected with its reason logged. | Algorithm (+ AI for repairs) |
| 7 Blind solver | A separate model gets only the ticket + base repo and writes its own patch. Graded, then diagnosed. | AI solver; algorithm diagnosis + AI judge |
| 8 Export | Write each package in the required package format (adapter for the final template). | Algorithm |
| 9 Report | Static HTML from the stored JSON: matrices, counterexamples, kill tables, costs, rejections. | Algorithm |

## 8. Validation gauntlet

All test runs happen in Docker from a clean checkout of the base commit plus the patch under test.

| Gate | Check | Pass condition |
|---|---|---|
| **G0 Baseline** | Existing suite on base | Green (known flaky tests listed and excluded identically everywhere) |
| **G1 Fail-before** | Grader on base. Every test is tagged `new` (defines the feature) or `preserved` (compatibility). | Every `new` test fails **for an expected reason**: an assertion failure, or the missing public API (`AttributeError`/`TypeError`/`NoSuchOption`/usage error) named in the contract. Collection errors, import errors in the test file itself, or broken fixtures never count. `preserved` tests pass on base. |
| **G2 Pass-after** | Grader + full existing suite on reference | All pass |
| **G3 Stability** | G1/G2 repeated 5× | Identical results |
| **G4 Public-API lint** | AST scan of grader imports and attribute access | No private names (`_x`), no reference-only helpers |
| **G5 Twin separation** | Pivot probe derived from the tickets, replayed through both real patches (below), then cross-grade | Each reference satisfies its own ticket's pivot expectation and violates its twin's; both graders contain the probe |
| **G6 Mutant kill** | For each requirement, ≥1 LLM-written "plausible wrong" patch violating exactly that requirement; plus mutmut on changed lines | Every requirement has a killed mutant; surviving mutants are either argued equivalent (logged) or trigger test repair |
| **G6h Held-out check** (measurement, not a repair input) | A separate set of incorrect patches written independently (member 4, or a separate model call that never feeds the repair loop), plus one **valid alternative implementation** per ticket | Report: how many wrong patches the **initial** grader accepted vs the **final** grader; the valid alternative must pass the final grader. This is the headline number for what the gauntlet adds. |
| **G7 Traceability** | Requirement ↔ test ↔ mutant links | Every requirement has ≥1 test and ≥1 killed mutant; every test cites a requirement |
| **G8 Novelty** | Feature not present in current source, docs or changelog | No match (grep + model check, logged) |
| **G9 Realism** | Rubric score (stakeholder reason, fits click's design) | Above threshold; human sign-off for showcase pairs |

### Pivot probe + differential search (G5 centrepiece)

**The rule: two patches disagreeing only proves they differ. Expected outcomes always come from the frozen tickets, never from a reference's output.** Otherwise incidental differences (punctuation, wording) get baked into the graders while the changed rule goes untested.

Example: ticket A says "report the first invalid value", ticket B says "report all invalid values". If the patches differ in punctuation even with one invalid value, naive differential search finds and "tests" that, and the cross-grade looks perfect while neither grader checks two invalid values.

G5 therefore needs three things:

1. **A pivot probe:** an input that actually exercises the changed rule (here, two invalid values in a known order). The contract stage writes it, together with an input grammar for the feature.
2. **Ticket-derived expectations:** for each ticket, a separate model call that sees **only that ticket** and the probe states the expected outcome as **semantic assertions** (A: exactly the first invalid value is reported; B: both are, in order). Anything the ticket leaves open (wording, punctuation, exit code if unspecified) stays unasserted.
3. **Replay through both real patched copies of click:** show what each version reported, check A meets A's assertions and fails B's, and vice versa, then export those assertions as tests into both graders.

Differential search then acts as a **lead finder**, not an oracle:

- Each reference gets its own worktree and a worker process that reads JSON lines `{argv, env, input}` and returns `{exit_code, output, exception_type}` via `click.testing.CliRunner`. Hypothesis generates invocations from the grammar and sends each to both workers.
- A disagreement is shrunk by Hypothesis to a **small** (not guaranteed shortest) example, then classified against the tickets:
  - on the pivot → a candidate extra probe; expectations again written from the tickets;
  - on a **shared** clause → one reference violates the shared contract, a bug to repair;
  - on behaviour the tickets leave open → ignored and logged.
- Every saved case is replayed in **fresh processes** before it counts, to rule out state leaking between persistent workers.
- If the budget runs out with no pivot difference, record **"no distinguishing case found within budget"** and reject the pair. That doesn't prove the pivot is unreachable.
- The demo button reads **"Find a small difference"**.

### Three-way diagnosis (stage 7)

When the blind solver's patch fails a grader:

1. Run differential search between the solver patch and the reference to get the shortest disagreeing input.
2. An AI judge gets **only** the ticket and that input with both outputs, and answers: does the ticket determine the correct output?
3. Classify:
   - **Solver mistake:** the ticket determines the output and the solver is wrong. The task stays as it is.
   - **Grader mistake:** the ticket allows the solver's behaviour. Fix or relax the test, re-run the gauntlet.
   - **Ambiguous ticket:** the ticket doesn't decide it. Offer two fixes: add the missing clause, or accept either outcome. Never silently invent a rule.
4. Judge verdicts are logged with the counterexample. Showcase pairs get a human check.

When the blind solver passes, that is solvability evidence without the reference.

## 9. Variation strategy

**Behaviour families for click** (candidate list; each must pass the novelty gate against current click source):

| Family | Example policy pair (verify novelty) |
|---|---|
| Conflict resolution | Mutually exclusive options: error vs last one wins |
| Source precedence | Value from env var vs default vs flag: which wins when combined with a new source |
| Repetition / accumulation | A repeated option: accumulate vs override vs error after N |
| Validation & error semantics | Report the first invalid value vs collect all invalid values |
| Lifecycle / ordering | Chained subcommand failure: stop the chain vs run the rest and report |
| Deprecation / compatibility | Deprecated alias: warn and accept vs reject with a hint |
| Retry / interaction | Prompt on invalid input: re-prompt N times vs fail immediately |

Rules:
- A pair varies **one** rule. A batch varies **families**.
- The final set covers ≥5 families; the report shows a coverage grid.
- Measured, not claimed: number of distinct files/functions touched across reference patches, and how many shared-clause tests overlap between pairs from different families (should be ~0).
- Cross-grade separation among **accepted** pairs is 100% by construction (G5 enforces it), so it is reported as a gate, not as a result. The held-out check (G6h) is the result.

## 10. Requirement-sensitivity experiment (impact)

Give tickets A and B to a solver model **in separate, blind runs** (neither run sees the twin, `pair_id` or hidden tests). Score in two steps:

1. **Shared requirements:** does each patch satisfy the shared clauses? Patches that fail here are reported as plain failures and excluded from step 2.
2. **Changed rule:** run both patches on the pivot probe and score each against its own ticket's assertions.

| | Grader A | Grader B |
|---|---|---|
| Patch for A | expect pass | expect fail on pivot |
| Patch for B | expect fail on pivot | expect pass |

Report what is observable, not why:
- the diagonal pattern;
- **"both patches produced the same outcome on the distinguishing case"** (and which ticket's rule that outcome matches);
- a patch passing both graders, which means investigate the graders (should be impossible after G5).

Report per model: shared-clause pass rate, pivot pass rate, same-outcome rate, and a few small reproducing invocations. Run on 2 models (one cheap, one strong) within budget.

## 11. Package layout (provisional until required package template is published)

Each package splits into what a solver may see and what only the evaluator sees.

```
packages/
  click-<family>-<slug>-A/
    task.md              # PUBLIC: ticket (Markdown) — the only thing a solver gets, plus the base repo
    env/
      Dockerfile         # pinned base image digest + locked dependencies (hashes)
      requirements.lock
    evaluator/           # HIDDEN from solvers
      meta.json          # repo, tag, base SHA, family, pivot clause id, pair_id, twin_package, model + cost, gate results
      solution.patch     # reference implementation
      tests/
        test_feature.py  # grader; each test tagged new/preserved + requirement ids
      regression.txt     # command for the existing suite + excluded flaky tests
      replay.sh          # one command that rebuilds env and reproduces every result below, no model calls
      patches/
        mutants/         # every G6 mutant patch
        heldout/         # G6h held-out wrong patches + valid alternative
        solver/          # blind-solver patches per model
      evidence/
        matrix.json      # G1–G3 basic validation matrix
        probe.json       # pivot probe, ticket-derived assertions, outputs of both references
        mutants.json     # which test killed each mutant
        heldout.json     # initial vs final grader acceptance
        trace.json       # requirement ↔ test ↔ mutant
        logs/            # raw pytest output per run
  click-<family>-<slug>-B/ ...
pairs/
  <slug>.json            # links A/B, pivot probe, cross-grade matrix (evaluator-side)
report/
  index.html             # static report, opens offline
demo/
  run_demo.sh            # executable demo command
```

Every result is reproducible offline with `replay.sh` (Docker + pytest). **Acceptance test for this:** a teammate who didn't generate the package runs `replay.sh` on their own machine with model access disabled and gets identical results. Only fresh generation needs API calls.

## 12. Demo script (pitch order)

1. **"We turn a real repository into new, runnable coding tasks."** Run one command on pinned click. Show the commit, the surface the factory found, and the two generated tickets. Highlight the one differing sentence.
2. **Basic validation matrix:** existing tests pass on base, feature tests fail on base, the reference passes both. (The required validation evidence.)
3. **The innovation:** show the pivot probe. The viewer reads the changed sentence and **predicts the result themselves**; the factory replays the probe through both real patched copies of click and confirms each matches its ticket. Then show M1: a wrong patch the initial grader accepted, the case the factory found, and the improved grader rejecting it while a different valid solution still passes.
4. **Break the grader:** a viewer types a click invocation; both patched versions run side by side. Press **"Find a small difference"**; Hypothesis shrinks and replays it in fresh processes; export it as a pytest file and run it.
5. **Fairness:** the blind solver's patch, and one example of each diagnosis (solver mistake / grader mistake / ambiguous ticket).
6. **A second family:** a different kind of rule (e.g. retry or ordering) to prove it's not one template.
7. **Numbers:** packages generated, gate pass/reject rates and reasons, mutant kill rate, cross-grade separation, requirement sensitivity of 2 models, cost per package.
8. **Limitations** (section 15), stated plainly.

A recorded backup video of the full demo is mandatory.

## 13. Architecture & stack

- **Orchestrator:** Python 3.12 CLI (`factory generate`, `factory validate`, `factory export`, `factory report`). Run state stored as JSON files per pair; no database.
- **Repo adapter:** one file for click: clone/pin, Docker image, test command, worker harness, public-API rules, surface discovery hints. A second repo means writing a second adapter file, nothing else.
- **Sandbox:** Docker per run, network off during tests, clean worktree per patch.
- **Model calls:** one `llm(prompt, model)` function; model names in config; token and cost logging on every call; hard cost cap per pair.
- **Search:** Hypothesis (generation + shrinking), persistent subprocess workers per worktree.
- **Mutation:** LLM requirement-targeted mutants (required) + mutmut limited to changed files (bonus).
- **Demo page:** small Streamlit app over the same functions (two side-by-side panels, invocation input, "shortest difference" button, export).
- **Report:** static HTML generated from the JSON evidence.

Reused open source (list in README): click, pytest, Hypothesis, mutmut, Docker, Streamlit, the model provider's SDK.

## 14. Team split

| Member | Owns | Answers |
|---|---|---|
| 1. Repo & execution | Adapter, Docker, baseline, worker harness, G0–G4, packaging/export, offline replay | "Can anyone reproduce this exact result from the starting commit?" |
| 2. Features & contracts | Surface map, seed + policy proposals, contracts, tickets, novelty & realism gates, family coverage | "Are these realistic tickets, and can a developer tell what each one allows?" |
| 3. Search & validation | Differential search, shrinking, cross-grading, counterexample → test, mutants, traceability | "What is the smallest observable case that separates these behaviours?" |
| 4. Independent evaluation & demo | Blind solver, diagnosis, requirement-sensitivity experiment, Streamlit demo, report, video | "Does it hold up on evidence its authors didn't design around, and can a judge inspect it?" |

Member 4 never authors reference patches for showcase packages, so they act as an internal independent reviewer.

## 15. Day-by-day plan

| Dates | Milestone |
|---|---|
| 24–25 Nov | Adapter + Docker + G0 green; worker harness; `llm()`; **one hand-made golden pair** end to end to fix file formats |
| 26–28 Nov | Stages 1–5 automated; G1–G4 automated; first generated pair passes |
| **by 1 Dec: Milestone M1** | **One automatically generated pair where the initial grader accepts a plausible wrong patch, the factory finds the missing case, and the improved grader rejects that patch while accepting a different valid solution.** Before and after runs saved. This is the proof the project rests on; it comes before scaling to more pairs. |
| 29 Nov – 1 Dec | Differential search + shrinking + cross-grade (G5); mutants + traceability (G6–G7); novelty/realism (G8–G9) |
| 2–3 Dec | Blind solver + diagnosis; sensitivity experiment on 2 models. **2 Dec: confirm package template and repo choice.** |
| 4 Dec | Generate final batch (target 8–12 pairs, ≥5 families); export in final template; report; demo page |
| 5–6 Dec | Freeze; README (setup, run, architecture, reused components, limitations); record backup video; submit |
| After 15 Dec (stretch) | Adaptive follow-ups: use surviving solver mistakes to generate targeted pairs; held-out pairs for measurement |

## 16. Metrics in the evidence report

- Pairs attempted / accepted / rejected, with rejection reason per gate
- Basic validation matrix per package (all must pass)
- **Held-out result (headline):** wrong patches accepted by initial vs final graders; valid alternatives accepted by final graders
- Pivot probes per pair; small-counterexample length; pairs rejected as "no distinguishing case found within budget"
- Mutant kill rate per requirement; equivalent mutants with justification
- Blind-solver pass rate; diagnosis counts (solver / grader / ambiguity)
- Requirement sensitivity per model
- Family coverage grid; patch diversity
- Tokens and cost per accepted package; wall time per stage

## 17. Honest limitations (to state in the final write-up)

- One repo validated end to end; carrying over to another means writing an adapter, which we did only for one (or two) repos.
- The AI judge in diagnosis can be wrong; showcase verdicts are human-checked, others are logged as model judgments.
- Differential search only explores the input grammar the contract declares; a difference outside it can be missed. Shrunk examples are small, not guaranteed shortest.
- Ticket-derived expectations come from a model reading the ticket; they're checked against both references and showcase probes are human-reviewed, but a shared misreading is possible.
- LLM mutants approximate real solver mistakes; they don't cover them all.
- The realism of features is partly a judgement call; the rubric plus human sign-off reduces but doesn't remove it.
- The sensitivity experiment covers a small number of models and pairs; it's a demonstration, not a benchmark result.

## 18. Left to the builder

- Prompt wording, repair-loop details, exact thresholds (realism score, cost cap, Hypothesis example budget).
- Internal module layout of the orchestrator.
- Which 8–12 policy pairs make the final set (within the family rules above).
- Styling of the report and demo page.

## 19. Calls made in this design (check these)

- **Starting commit:** the **provided starter kit is the authority** for the base revision, export format and benchmark protocol. If it names a click revision, record it here and pin it. If not, pin click's latest stable release tag on 24 Nov. Re-pinning early is cheap (adapter + G0 only).
- **Novelty scope (G8):** check against upstream `main` (not just our tag), the docs, CHANGES, and open PR/issue titles at generation time. Anything that landed upstream after our tag counts as existing and is rejected.
- **How twins count for Variation:** we count a twin pair as **one feature** when claiming variation. Variation is claimed from the spread of families (≥5) and features; twins are presented as validation and sensitivity evidence. A and B are still standalone packages.
- **Twin link survives any template:** each package's `meta.json` carries `pair_id`, `twin_package` and `pivot_clause`, so the twin evidence reaches reviewers even if the required template has no place for `pairs/`.
- **Budget fallbacks, in cut order:** (1) drop mutmut, keep LLM mutants; (2) the sensitivity experiment runs on one model; (3) the blind solver uses the same model as the references but a fresh context and only the ticket; (4) cut the target to 6 pairs.

## 20. Open items

- Final package template: confirm by 2 Dec; export stage adapts to it.
- Which model provider the credits cover, and how much; set the default models once known (fallbacks above apply if small).
- Base revision and export template: take from the provided starter kit.

Settled: team of 4, split as in section 14.

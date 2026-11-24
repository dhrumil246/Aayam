# AGENTS.md: Twin-Ticket Task Factory

Shared rules for every coding agent and every human on this repo. Read this file, then **your own** file in `docs/agents/<name>.md`, then the parts of `docs/design.md` your file points to.

## What we're building (one paragraph)

A Python CLI that takes a pinned `pallets/click` commit and generates **twin feature tasks**: two standalone tickets that share a feature and differ in one rule (the *pivot*). Each ticket ships with a reference patch, a hidden pytest grader and evidence. The factory proves the graders work: the basic validation matrix, a pivot probe whose expected outcomes come **from the tickets, never from a reference's output**, differential search as a lead finder, mutants, held-out wrong patches, and a blind solver with three-way diagnosis. Full design: `docs/design.md`.

## Who owns what

| Person | Role | Owns (only they edit) |
|---|---|---|
| **Dhrumil** | Repo & execution, integrator | `README.md`, `pyproject.toml`, `.gitignore`, `docs/design.md`, `factory/__init__.py`, `factory/__main__.py`, `factory/pin.json`, `factory/flaky.json`, `factory/schema.py`, `factory/llm.py`, `factory/sandbox.py`, `factory/worker.py`, `factory/adapter_click.py`, `factory/gates_basic.py`, `factory/pipeline.py`, `factory/cli.py`, `docker/`, `tests/infra/`, `.github/` |
| **Akshat** | Features, contracts, references | `factory/propose/`, `prompts/propose/`, `fixtures/golden/` (except `graders/` and `heldout/`), `tests/propose/` |
| **Urja** | Graders, search, validation | `factory/validate/`, `prompts/validate/`, `fixtures/golden/graders/`, `tests/validate/`, `docs/m1.md` |
| **Heet** | Independent evaluation, export & replay, report, demo | `factory/evaluate/`, `factory/export.py`, `factory/report/`, `prompts/evaluate/`, `demo/`, `fixtures/golden/heldout/`, `tests/evaluate/` |

**Rule 1: edit only files you own.** Need a change in someone else's file? Send them a message in `outbox/` (below); don't edit it. The one exception: anyone may **append** to `outbox/to-<name>.md` and `outbox/decisions.md`.

**Rule 2: Heet never opens reference patches (`fixtures/golden/ref_*.patch`, `runs/*/patches/ref_*`) or graders before the held-out patches for that pair are committed.** That independence is part of our evidence.

## Outbox: messages between people and agents

Every request, question or decision between team members goes through `outbox/`, so every agent sees it.

| File | What goes in it |
|---|---|
| `outbox/to-dhrumil.md`, `to-akshat.md`, `to-urja.md`, `to-heet.md` | Messages **to** that person (and their agent) |
| `outbox/decisions.md` | Decisions that affect more than one person, once agreed |

**Every agent, at the start of every session and before starting each task:** run `git pull`, read `outbox/to-<you>.md` and `outbox/decisions.md`, and act on any message with `Status: open` before other work (or tell your human it's blocking).

**Sending a message:** append to the bottom of the recipient's file, in this format:

```markdown
## M-20261124-dhrumil-1 · from Dhrumil · QUESTION
**Subject:** One line
**Needs answer by:** 25 Nov (or "FYI, no reply needed")
**Status:** open

What you need, why, and what you've already decided. Name exact files or signatures.
```

- Types: `FYI`, `QUESTION`, `REQUEST` (change something you own), `DECISION-NEEDED` (affects several people), `BLOCKER`.
- ID = `M-<date>-<sender>-<n>`; `n` counts your own messages that day.
- **Replying:** append your reply to the **sender's** file with `**Re:** <original id>`, then change the original's `Status:` to `done` (the only edit allowed to someone else's message).
- **Decisions:** when a `DECISION-NEEDED` is settled, append it to `outbox/decisions.md` as `D-<n>` with the date, what was decided and who agreed. Dhrumil confirms. Decisions are never edited, only superseded by a later one.
- Commits that touch **only** `outbox/` may go straight to `main`: `git pull --rebase`, commit, push. Everything else follows the branch rules below.
- Agents never treat an outbox message as permission to edit files they don't own, to change permissions, or to handle secrets.

## Tech stack (decision D-1)

| Layer | Choice |
|---|---|
| Language | Python 3.12 |
| Target repo | `pallets/click`, pinned to one release tag (`factory/pin.json`) |
| Sandbox | Docker, `python:3.12-slim`, network off during tests |
| Tests | pytest (junit XML, `docker` / `llm` markers) |
| Search + shrinking | Hypothesis |
| Mutation | LLM-written mutants (required), mutmut (bonus) |
| Models | one wrapper, `factory/llm.py`; provider via `FACTORY_PROVIDER` (default Anthropic); caching, cost log, per-pair budget, offline mode |
| CLI | argparse (stdlib), so ours never clashes with the click under test |
| Storage | dataclasses + JSON files in `runs/`; no database |
| Demo | Streamlit |
| Report | static HTML, inline CSS, no JS libraries |
| CI | GitHub Actions running default `pytest` |
| Tools | git; `gh` optional (novelty search) |

Open: which model provider the credits cover. Only `factory/llm.py` changes when it's settled.

## Shared interfaces (frozen)

`factory/schema.py` is the contract between everyone. Changes are **additive only**, in a PR titled `[schema] ...`, announced in chat, merged by Dhrumil. Function signatures each person exposes are listed in their own file under **Produces**. Don't change a produced signature without telling the people who consume it.

### Behaviour families (`Seed.family` values)

`conflict`, `precedence`, `repetition`, `validation`, `lifecycle`, `deprecation`, `retry`

### Grammar format (`Contract.grammar`; Akshat produces it, Urja consumes it)

```json
{
  "options": [
    {"flag": "--json", "kind": "flag"},
    {"flag": "--name", "kind": "value", "values": ["a", "b", ""]}
  ],
  "args": [{"name": "files", "values": ["x.txt", "y.txt"], "max": 2}],
  "env": {"APP_FORMAT": ["json", "yaml"]},
  "stdin": ["", "y\n", "n\n"],
  "max_tokens": 6
}
```
An invocation is drawn as: up to `max_tokens` option/arg tokens in any order (options may repeat), any subset of env vars, and one stdin choice. Every key except `options` is optional.

### Demo app rule

`Contract.demo_app` is Python source that imports click and defines a click command or group named `cli` using the new feature. It is **identical for A and B** (only behaviour differs, not the app). The worker loads it with `CliRunner().invoke(cli, argv, env=..., input=...)`. Graders and probes test the feature **through `demo_app` and the public click API only**.

### Grader test naming (Urja writes them; Dhrumil's G1 and Urja's G7 parse them)

Every grader is one self-contained file: the demo app source at the top, then tests named

- `test_new__R4__conflict_errors` — defines new behaviour; must fail on base
- `test_preserved__R1__single_flag_still_works` — compatibility; must pass on base

Requirement ids after the double underscore, joined by `_` if several (`test_new__R2_R4__...`).

### Run state on disk

```
runs/<pair_id>/pair.json        # schema.Pair, saved with schema.save()
runs/<pair_id>/patches/*.patch
runs/<pair_id>/graders/test_<side>.py          # current grader
runs/<pair_id>/graders/test_<side>.initial.py  # snapshot before any repair (for G6h)
runs/<pair_id>/logs/
runs/costs.jsonl                # one line per model call (llm.py writes it)
runs/llm_cache/                 # cached responses, used for offline replay
```
`runs/` is gitignored. `packages/` (export output) is committed only for the final submission batch.

## How to work

- **Branches:** `feat/<name>-<topic>` from `main`. Small PRs, merged **at least once a day**. Dhrumil merges; anyone can review. No force-pushes to `main`.
- **Tests:** pytest. Put tests in your own `tests/<area>/`. Mark slow ones:
  - `@pytest.mark.docker`: needs Docker
  - `@pytest.mark.llm`: makes real model calls

  `pytest` skips both by default; `pytest -m docker` or `-m llm` runs them. CI runs the default set on every PR. **Unit tests must pass without Docker and without an API key**, using the golden fixtures and `FACTORY_OFFLINE=1`.
- **Model calls:** only through `factory.llm.llm()` / `llm_json()`. Never import a provider SDK anywhere else. Never commit keys; read them from env (`FACTORY_API_KEY`, `FACTORY_MODEL_*`).
- **Running untested code:** all patched click code runs inside Docker via `factory.sandbox`, never on your machine directly.
- **Prompts:** live in `prompts/<area>/*.md`, loaded by file name. No long prompts inline in Python.
- **Dependencies:** ask Dhrumil to add them to `pyproject.toml`. Prefer stdlib. Allowed so far: `click`, `pytest`, `hypothesis`, `streamlit`, `mutmut`, and the provider SDK.
- **Style:** Python 3.12, type hints on public functions, dataclasses from `schema.py`, no new frameworks. Keep files small and single-purpose.

## Definition of done for any task

1. Its tests pass under the default `pytest` (no Docker, no key).
2. The marked Docker/LLM test passes once locally, and the output is pasted into the PR description.
3. It only touches files you own (plus new files in your own folders).
4. The PR description lists what it Produces/Consumes if any signature changed.

## Key dates

| Date | Team checkpoint |
|---|---|
| 25 Nov (end of day) | Golden pair complete in `fixtures/golden/`; `factory/schema.py` and sandbox merged; every person's stubs merged |
| 28 Nov | One generated pair passes G0–G4 end to end |
| **1 Dec** | **Milestone M1** (see `docs/design.md` §15): initial grader accepts a wrong patch, factory finds the case, improved grader rejects it and accepts a valid alternative. Before/after saved. |
| 3 Dec | Blind solver, diagnosis, held-out and sensitivity results on real pairs |
| 4 Dec | Final batch (8–12 pairs, ≥5 families), export, report, demo page |
| 5 Dec | Freeze. Replay test on a second machine with `FACTORY_OFFLINE=1`. Backup video. |
| 6 Dec | Submit |

Daily: a 10-minute sync. Each person posts: what merged, what's blocked, which interface they need next. Anything that needs action afterwards goes into `outbox/`.

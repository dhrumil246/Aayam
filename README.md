# Aayam: Twin-Ticket Task Factory

Deadline: 6 Dec 2026.

We turn `pallets/click` into new, runnable feature tasks. Tasks come in **twins**: two standalone tickets that differ in one rule. The factory finds the exact case a grader must check to tell them apart, and proves its tests reject plausible wrong implementations.

## Setup

Needs Python 3.12, git, and Docker Desktop (running).

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv -e '.[dev,llm]'
```

or, without uv: `python3.12 -m venv .venv && .venv/bin/pip install -e '.[dev,llm]'`.

```bash
.venv/bin/python -m pytest              # fast tests: no Docker, no API key
.venv/bin/python -m pytest -m docker    # sandbox tests; first run builds the pinned image (~2 min)
.venv/bin/python -m pytest -m llm       # real model calls (needs FACTORY_API_KEY)
```

### Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `FACTORY_API_KEY` | unset | Model provider key. Never commit it. |
| `FACTORY_PROVIDER` | `anthropic` | Provider used by `factory/llm.py` |
| `FACTORY_MODEL_DEFAULT` | `claude-opus-5-5` | Model when a stage doesn't name one |
| `FACTORY_OFFLINE` | unset | `1` = serve model calls from the cache only; never contact a provider |
| `FACTORY_PAIR_BUDGET_USD` | `5` | Spending cap per pair |
| `FACTORY_RUNS` | `runs` | Where run state, caches and logs go |

## Commands

```bash
.venv/bin/python -m factory generate --family conflict [--n 3] [--pair-id ID]   # generate + validate twin pairs (resumable)
.venv/bin/python -m factory evaluate PAIR_ID --models claude-sonnet-5-5,claude-opus-5-5   # blind solver + diagnosis
.venv/bin/python -m factory export --all [--out packages]                      # write task packages for accepted pairs
.venv/bin/python -m factory report [--out report/index.html]                   # static evidence report
.venv/bin/python -m factory replay packages/<package>                          # re-run all evidence, zero model calls
```

Families: `conflict`, `precedence`, `repetition`, `validation`, `lifecycle`, `deprecation`, `retry`.

## Architecture

```
 pin click 8.5.1 ─▶ surface map ─▶ seed + policy pair ─▶ G8 novelty ─▶ G9 realism
                                                                   │
     contracts A/B ─▶ tickets A/B ─▶ held-out patches (ticket only) ─▶ reference patches A/B
                                                                   │
     ticket-derived expectations ─▶ graders A/B (+ initial snapshot)
                                                                   │
     gauntlet: G1 fail-before · G2 pass-after · G3 stability · G4 public API
               G5 pivot probe + cross-grade · G6 mutants · G7 traceability
               ── failure ─▶ repair (max 2) ─▶ else reject with reason
                                                                   │
     G6h held-out check (measurement only) ─▶ accepted ─▶ blind solver + diagnosis ─▶ export ─▶ report
```

- **Patched code only runs in Docker:** `python:3.12-slim` pinned by digest, a hash-locked `docker/requirements.lock`, network off ([factory/sandbox.py](factory/sandbox.py), [factory/worker.py](factory/worker.py)).
- **One model door:** [factory/llm.py](factory/llm.py). It caches responses, logs cost, caps spending per pair and has an offline mode.
- **Orchestration:** [factory/pipeline.py](factory/pipeline.py) runs every stage and saves state to `runs/<pair_id>/`, so killed runs resume.
- Full design: [docs/design.md](docs/design.md). Decisions: [outbox/decisions.md](outbox/decisions.md).

## Reused open source

click (the target repo), pytest, Hypothesis, mutmut (optional), Docker, Streamlit (demo), the Anthropic Python SDK, uv (setup and lock generation).

## Limitations

- One repo validated end to end. Carrying over means writing a new `factory/adapter_<repo>.py`.
- The AI judge in diagnosis can be wrong. Showcase verdicts are human-checked; the rest are logged as model judgments.
- Ticket-derived expectations come from a model reading the ticket. They are checked against both references, but a shared misreading is possible.
- Differential search only explores the declared input grammar. Shrunk examples are small, not guaranteed shortest.
- LLM mutants approximate real solver mistakes; they don't cover all of them.
- 24 click pager tests that need the `less` binary are excluded (`adapter_click.ENV_EXCLUDED`).
- The sensitivity experiment covers few models and pairs. It's a demonstration, not a benchmark result.

## Team: start here

1. Read [AGENTS.md](AGENTS.md): who owns which files, shared interfaces, branch and test rules, key dates.
   Then read your messages in [outbox/](outbox/) (`to-<your-name>.md` and `decisions.md`). Check them at the start of every session.
2. Read your own plan and hand it to your coding agent:

   | Person | Role | Plan |
   |---|---|---|
   | Dhrumil | Repo, sandbox, worker, pipeline, CLI | [docs/agents/dhrumil.md](docs/agents/dhrumil.md) |
   | Akshat | Features, contracts, tickets, reference patches | [docs/agents/akshat.md](docs/agents/akshat.md) |
   | Urja | Graders, search, validation, Milestone M1 | [docs/agents/urja.md](docs/agents/urja.md) |
   | Heet | Held-out patches, blind solver, diagnosis, export and replay, report, demo | [docs/agents/heet.md](docs/agents/heet.md) |

3. The full design is in [docs/design.md](docs/design.md) (also [docs/design.html](docs/design.html) for reading in a browser).
4. Shared data types live in [factory/schema.py](factory/schema.py).
5. Branch as `feat/<name>-<topic>` and open small PRs against `main`.

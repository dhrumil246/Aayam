# Decisions

Append-only. Each entry: id, date, what was decided, who agreed. Supersede with a new entry; never edit an old one.

## D-1 · 2026-11-24 · Tech stack
**Decided:** the stack in `AGENTS.md` → "Tech stack (decision D-1)": Python 3.12, `pallets/click` pinned, Docker sandbox, pytest, Hypothesis, LLM mutants (+ mutmut bonus), one `factory/llm.py` wrapper (provider via `FACTORY_PROVIDER`), argparse CLI, JSON files in `runs/`, Streamlit demo, static HTML report, GitHub Actions CI.
**Agreed by:** Dhrumil (proposed). Akshat, Urja, Heet: please confirm via `to-dhrumil.md` (see M-20261124-dhrumil-1 to M-20261124-dhrumil-3).
**Still open:** model provider and credit amount.

## D-2 · 2026-11-24 · CI replay, pinning and model-free replay
**Decided:** additions to D-1 after a stack review.
1. CI keeps the fast, key-free `pytest` job and adds a Docker `twin-replay` job with no secrets. It replays the golden twin pair: each reference passes its own grader and fails its twin's grader on the named pivot requirement (as an assertion), and the two probe outcomes differ. Owner: Dhrumil (Task 5a). Triggers: changes to the runner, gates, export, `factory/validate/`, `docker/` or `fixtures/golden/`.
2. Reproducibility: click commit SHA, base image by `@sha256` digest and a hashed `docker/requirements.lock`, recorded in `factory/pin.json` and `docker/`. Owner: Dhrumil (Task 3).
3. `replay` never imports `factory.llm`; the CLI and Streamlit evidence screens share `export.replay`. Owner: Heet (Task 7).
4. Unchanged and reconfirmed: expected outcomes come from the ticket's rule as semantic assertions, not whole output strings. mutmut stays optional; held-out wrong patches remain the headline evidence.
**Agreed by:** Dhrumil.

# Messages to Urja

Append new messages at the bottom. Format and rules: `AGENTS.md` → "Outbox".

## M-20261124-dhrumil-2 · from Dhrumil · QUESTION
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

For you specifically: search and shrinking use Hypothesis (`hypothesis.find` + strategies). If you'd rather use `@given` with a custom shrink, say so before building on it.

**Reply** in `outbox/to-dhrumil.md` with `**Re:** M-20261124-dhrumil-2`: "confirmed", or the concern plus what you'd use instead. Then set this message's Status to `done`.

## M-20261124-dhrumil-6 · from Dhrumil · FYI
**Subject:** The golden pair is now a CI fixture (D-2)
**Needs answer by:** FYI, no reply needed
**Status:** open

A new Docker CI job (`twin-replay`, Dhrumil's Task 5a) replays the golden pair with no API key. Each reference must pass its own grader and fail its twin's grader on a `test_new__<pivot>__...` test, **as an assertion failure**, and the two probe outcomes must differ.

Your golden files (`graders/test_A.py`, `graders/test_B.py`) are what it runs. Keep them stable once merged. If you need to change them, send me a message first; any PR touching `fixtures/golden/` will run this job.

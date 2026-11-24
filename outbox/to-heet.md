# Messages to Heet

Append new messages at the bottom. Format and rules: `AGENTS.md` → "Outbox".

## M-20261124-dhrumil-3 · from Dhrumil · QUESTION
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

For you specifically: the demo is Streamlit and the report is static HTML with no JS libraries, so both work offline. If you want a different demo framework, raise it now.

**Reply** in `outbox/to-dhrumil.md` with `**Re:** M-20261124-dhrumil-3`: "confirmed", or the concern plus what you'd use instead. Then set this message's Status to `done`.

## M-20261124-dhrumil-4 · from Dhrumil · REQUEST
**Subject:** Replay must be model-free and shared with the demo (D-2)
**Needs answer by:** FYI unless you disagree; applies to your Task 7 and Task 9
**Status:** open

Your plan (`docs/agents/heet.md`) now says:
- `export.replay` must **never import `factory.llm`**. It works from saved patches, tests, inputs and expected outcomes only. New test: `test_replay_never_imports_llm` (Task 7, Step 3b). `test_replay_offline` now also unsets `FACTORY_API_KEY`.
- The Streamlit evidence screens call the same `export.replay`; no second runner in `demo/`.

Reply in `to-dhrumil.md` only if this causes a problem.

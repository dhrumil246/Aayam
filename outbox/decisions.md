# Decisions

Append-only. Each entry: id, date, what was decided, who agreed. Supersede with a new entry; never edit an old one.

## D-1 · 2026-11-24 · Tech stack
**Decided:** the stack in `AGENTS.md` → "Tech stack (decision D-1)": Python 3.12, `pallets/click` pinned, Docker sandbox, pytest, Hypothesis, LLM mutants (+ mutmut bonus), one `factory/llm.py` wrapper (provider via `FACTORY_PROVIDER`), argparse CLI, JSON files in `runs/`, Streamlit demo, static HTML report, GitHub Actions CI.
**Agreed by:** Dhrumil (proposed). Akshat, Urja, Heet: please confirm via `to-dhrumil.md` (see M-20261124-dhrumil-1 to M-20261124-dhrumil-3).
**Still open:** model provider and credit amount.

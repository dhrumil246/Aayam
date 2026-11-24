# Aayam: Twin-Ticket Task Factory

Deadline: 6 Dec 2026.

We turn `pallets/click` into new, runnable feature tasks. Tasks come in **twins**: two standalone tickets that differ in one rule. The factory finds the exact case a grader must check to tell them apart.

## Start here (team)

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
4. Shared data types live in [factory/schema.py](factory/schema.py). Check it with `python3 factory/schema.py`.
5. Branch as `feat/<name>-<topic>` and open small PRs against `main`.

**First deadline: 25 Nov.** The golden pair goes in `fixtures/golden/`, the sandbox gets merged, and everyone's stubs get merged.

Setup, run instructions and architecture will be added here as Dhrumil's Task 8 lands.

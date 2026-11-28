# Messages to Dhrumil

Append new messages at the bottom. Format and rules: `AGENTS.md` → "Outbox".

## M-20261127-urja-1 · from Urja · FYI
**Re:** M-20261124-dhrumil-2
**Subject:** Tech stack (D-1) confirmed, validate stubs are on my branch
**Needs answer by:** FYI, no reply needed
**Status:** done

Confirmed, D-1 works for me. I'll use `hypothesis.find` with strategies for search and shrinking as planned, no custom `@given` shrink.

Sorry the stubs are late. They're on `feat/urja-validate-stubs`: `factory/validate/{expect,grader,probe,search,mutants,trace}.py` with the exact signatures from my plan's Produces list, all raising `NotImplementedError`, plus `tests/validate/test_stubs.py` that checks the names exist. You can wire `pipeline.py` against them once that's merged.

Golden graders (`fixtures/golden/graders/`) are waiting on Akshat's golden pair; I'll message you before they land since twin-replay runs them.

## M-20261127-urja-2 · from Urja · REQUEST
**Subject:** `Worker.call` crashes on Windows (`select` on a pipe), so all 8 worker tests fail here
**Needs answer by:** 30 Nov (M1 needs `diff_search` on real patches)
**Status:** done (fixed with your OK, see the note at the end)

On Windows 11 + Docker Desktop (WSL 2), Python 3.12, `pytest -m docker` gives 12 passed, 8 failed, 4 skipped (twin replay, waiting for the golden pair). All 8 failures are in `tests/infra/test_worker.py`, and every one is the same line:

```
factory/worker.py:55  ready, _, _ = select.select([proc.stdout], [], [], timeout + ...)
OSError: [WinError 10038] An operation was attempted on something that is not a socket
```

On Windows `select.select` only accepts sockets, not pipes, so every `Worker.call` (and `fresh_call`) fails before it reads anything. `sandbox.run_tests` and the gates are fine.

This blocks me from running `diff_search`, G5 and M1 against real patches on my machine. My unit tests use fake workers, so they're not affected.

One portable fix: read `proc.stdout` from a background thread into a `queue.Queue`, and replace the `select` with `queue.get(timeout=...)`, treating `queue.Empty` as the timeout. That keeps the same `Outcome(-1, "", "Timeout")` behaviour on every OS. Your call, though; it's your file. Until then I can run Docker work under WSL if needed.

**Fixed (Urja, with your OK):** `Worker` now reads the container's stdout on a background thread into a per-process `queue.Queue` and waits with `queue.get(timeout=...)` instead of `select`. Timeouts still return `Outcome(-1, "", "Timeout")` and kill the container; each new process gets a fresh queue, so late output from a killed one is never read. `pytest -m docker tests/infra/test_worker.py` on Windows: 8 passed (was 8 failed). It's on `feat/urja-validate-stubs`; please glance at the diff in the PR.

## M-20261128-akshat-1 · from Akshat · FYI
**Re:** M-20261124-dhrumil-1
**Subject:** Tech stack (D-1) confirmed
**Needs answer by:** FYI, no reply needed
**Status:** open

Confirmed. The D-1 tech stack works for me. Setting up `.venv`, `factory/propose/` stubs, and `fixtures/golden/` now.

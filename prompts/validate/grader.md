You are writing the hidden pytest tests for one feature ticket for the Python library `click`. A developer will implement the ticket; your tests decide whether their implementation meets it. Write them from the ticket and the requirements below only.

## Ticket (what the developer sees)

{ticket}

## Requirements

{requirements}

Left open on purpose (never test these):

{open_items}

New public API:

```
{public_api}
```

## What the test file already contains

The file starts with this demo app as a string named `DEMO_APP`, and two helpers. You don't write these; just use them.

```python
{demo_app}
```

- `run(argv, env=None, input=None)` builds the demo app and invokes it with `click.testing.CliRunner`. It returns an object with `exit_code` (int), `output` (str, stdout and stderr together) and `exception_type` (str or None).
- `load_cli()` returns the demo app's `cli` command.
- `click`, `CliRunner` and `types` are already imported.

A test for {pivot_id} that runs the main example for that rule is added automatically after your tests. You may still add more {pivot_id} tests for other cases the ticket determines.

## Rules

1. Name every test `test_new__<ids>__<what>` or `test_preserved__<ids>__<what>`, where `<ids>` are requirement ids joined by `_` (e.g. `test_new__R2_R4__...`). Every requirement above needs at least one test, and {pivot_id} needs at least one `test_new__` test.
2. `test_new__` tests check the new behaviour. They must **fail on click without this feature**: with the demo app, `run()` raises there, which is fine. Never write a `test_new__` test that would pass on today's click, e.g. one that only checks `exit_code == 0`.
3. `test_preserved__` tests check that existing behaviour still works. They must **pass on today's click**, so they must not use the new API or the demo app. Define a small click command inside the test that doesn't use the feature.
4. Use only click's public API (`click.*`, `click.testing.CliRunner`). No names starting with `_`, no internal modules.
5. Assert only what the ticket and requirements determine. Don't assert exact error wording, punctuation or anything listed as left open. Prefer checks like "the option name appears in the output" or "exit code is 2" when the ticket says so.
6. No `pytest.mark.skip`, `skipif`, `xfail` or `pytest.skip`. No fixtures, no files, no network, no randomness. Each test must be quick and give the same result every time.
7. Don't redefine `DEMO_APP`, `run` or `load_cli`, and don't repeat the imports above.

Reply with only the test functions, in one ```python block.

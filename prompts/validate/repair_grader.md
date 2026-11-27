You wrote hidden pytest tests for one feature ticket for the Python library `click`. A validation check on those tests failed. Fix the tests, using the ticket and requirements below as the only source of truth.

## Ticket

{ticket}

## Requirements

{requirements}

Left open on purpose (never test these):

{open_items}

New public API:

```
{public_api}
```

## Demo app

The test file stores this as the string `DEMO_APP`. `run(argv, env=None, input=None)` invokes it and returns an object with `exit_code`, `output` and `exception_type`; `load_cli()` returns its `cli` command. `click`, `CliRunner` and `types` are imported. Tests for {pivot_id} named `test_new__{pivot_id}__pivot_...` are generated separately and kept as they are.

```python
{demo_app}
```

## What failed

{failure}

How to read common failures:

- A `test_new__` test **passed on click without the feature**: it doesn't actually check the new behaviour. Make it assert something only the new behaviour produces.
- A `test_preserved__` test **failed on click without the feature**: it uses the new API or the demo app. Rewrite it with its own small command that doesn't use the feature.
- A test **failed on a correct implementation**: it asserts something the ticket doesn't require (often wording or something left open). Relax it to what the ticket states.
- An implementation that breaks a requirement **passed every test**: add or strengthen a test for that requirement.
- A collection or syntax error: fix the code.

## Current tests

```python
{tests}
```

## Rules

1. Keep test names in the form `test_new__<ids>__<what>` / `test_preserved__<ids>__<what>`. Every requirement keeps at least one test.
2. Keep tests that are fine. Change only what the failure points to, plus anything else that clearly breaks the rules here.
3. Public click API only, no `_` names, no skip or xfail, deterministic and quick.
4. Never weaken a test so that a wrong implementation would pass; make it match the ticket.

Reply with the full corrected tests section (all test functions, not the helpers or the generated {pivot_id} pivot tests), in one ```python block.

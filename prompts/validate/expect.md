You are writing the expected outcome of one command-line run, using only a feature ticket.

The ticket below describes a new feature for the Python library `click`. A small click app called `cli` uses that feature. It will be run once with the input shown, and you must say what the ticket requires about the result, for requirement {requirement_id}.

## Ticket

{ticket}

## The run

- argv: {argv}
- environment variables: {env}
- stdin: {stdin}

The result is an object named `outcome` with three fields:

- `outcome.exit_code`: int
- `outcome.output`: str (stdout and stderr together)
- `outcome.exception_type`: str or None (name of an uncaught exception, if any)

## What to write

A JSON list of checks. Each check has a short `description` and a `python` boolean expression over `outcome`.

Rules:

1. Assert only what the ticket **determines** for this run. If the ticket leaves something open (exact wording, punctuation, capitalisation, help text, an exit code it doesn't state), don't assert it.
2. Prefer semantic checks over whole strings: a value or option name appearing in the output, the order of two values, an exit code the ticket names. Never compare the full output to a fixed string.
3. Every check must look at `outcome`. No checks that are always true.
4. Each `python` expression may only use: the name `outcome`; its fields `exit_code`, `output`, `exception_type`; string, number, bool and None literals and tuples of them; comparisons (`==`, `!=`, `<`, `<=`, `>`, `>=`, `in`, `not in`, `is None`, `is not None`); `and`, `or`, `not`; `len()`; and the string methods `lower`, `count`, `find`, `strip`, `splitlines`. Nothing else: no indexing, no other functions or methods, no keyword arguments.
5. If the ticket determines nothing about this run for requirement {requirement_id}, reply with an empty list `[]`.

Reply with JSON only, for example:

```json
[
  {{"description": "a usage error", "python": "outcome.exit_code == 2"}},
  {{"description": "the message names both options", "python": "'--a' in outcome.output and '--b' in outcome.output"}}
]
```

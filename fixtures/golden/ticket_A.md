# Add a conflicts_with parameter to click

## Background

Add a conflicts_with parameter to click.Option (and click.option) accepting a sequence of other option names or flags that conflict with this option.

Automated scripts should fail loudly when given contradictory flags instead of silently guessing which one the caller meant.

## Requirements

1. **R1:** click.Option and click.option accept a conflicts_with parameter (a sequence of option names or option flags, or None).
2. **R2:** When only one of the conflicting options is passed on the command line, it behaves identically to an option without conflicts_with.
3. **R3:** Options not listed in conflicts_with are unaffected and may be combined freely with conflicting options.
4. **R4:** Combining conflicting options on the command line raises a usage error (exit code 2) whose message names both conflicting options.

## Public API

```python
click.Option(..., conflicts_with: Sequence[str] | None = None)
click.option(..., conflicts_with: Sequence[str] | None = None)
```

## Left to you

- Exact error message wording when conflicting options are combined (provided both conflicting option names appear).
- Whether --help output mentions option conflicts.

## How it will be checked

- Existing `click` tests must continue to pass.
- New tests will invoke a `click` command using `CliRunner` and the public `click` API.

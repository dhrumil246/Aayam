You are helping test the hidden tests for a feature ticket for the Python library `click`. Below is the ticket and a correct implementation of it, as a unified diff against click's source.

Write a **different implementation** of the same feature: the most plausible one a careful developer might actually ship, which meets every requirement **except {requirement_id}**. It should break {requirement_id} in a realistic way (a misread rule, a missed case, an off-by-one, the wrong order), not by deleting the feature or crashing.

## Ticket

{ticket}

## The requirement your implementation must break

- {requirement_id}: {requirement}

## Requirements it must still meet

{others}

## Public API it must keep

```
{public_api}
```

## The correct implementation

```diff
{reference}
```

## Rules

1. Reply with one complete unified diff against the **original** click source (the same base the correct implementation applies to), not a diff on top of it. Use `--- a/...` / `+++ b/...` headers and `@@` hunks.
2. Keep the same public API, so code using the feature still loads.
3. Only {requirement_id} may behave differently from the ticket. Everything else, including click's existing behaviour, must keep working.
4. No comments that say the code is wrong, and no dead code.

Reply with the diff in one ```diff block.

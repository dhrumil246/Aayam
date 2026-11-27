Two tickets, A and B, describe the same new feature for the Python library `click`. They share most requirements and differ in exactly one rule (the pivot). Two implementations, one written for each ticket, were run on the same input and gave different results.

Decide what this difference is about, judging **only by what the tickets say**. The results show what each implementation did; they are not the source of truth.

## Ticket A

{ticket_a}

## Ticket B

{ticket_b}

## The input

- argv: {argv}
- environment variables: {env}
- stdin: {stdin}

## Result of the implementation for A

{outcome_a}

## Result of the implementation for B

{outcome_b}

## Labels

- `pivot`: the input exercises the rule where A and B differ, and the tickets require different results here.
- `shared`: the tickets agree on what must happen for this input, so at least one implementation breaks a shared requirement.
- `open`: the difference is only in something the tickets leave unspecified (wording, punctuation, capitalisation, an exit code neither ticket states, help text).

If a case looks like both `pivot` and `open` (the rule is exercised but the only visible difference is wording the tickets leave open), choose `open`.

Reply with JSON only:

```json
{{"label": "pivot", "reason": "one sentence"}}
```

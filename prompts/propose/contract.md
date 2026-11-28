Generate frozen twin contracts A and B for this `pallets/click` feature seed.

Seed:
- pair_id: {pair_id}
- family: {family}
- feature: {feature}
- policy_a: {policy_a}
- policy_b: {policy_b}

Click surface map:
{surface}

Rules:
1. Both contracts must have identical `demo_app`, `grammar`, `probe`, `public_api`, and non-pivot `requirements`.
2. Each contract must have **exactly one** requirement with `"pivot": true`, and both pivots must have the same `id` (e.g. `"R4"`).
3. `demo_app` must be valid Python that imports `click`, defines a top-level `cli` command or group using the new feature, and prints plain text (no ANSI colour or terminal width assumptions).
4. Every token in `probe.argv` must be drawable from `grammar`, and `probe` must trigger the pivot difference between A and B.
5. `open_items` lists behaviours deliberately left unspecified.

{feedback}

Reply with JSON only:
{{
  "A": {{ ...Contract fields... }},
  "B": {{ ...Contract fields... }}
}}

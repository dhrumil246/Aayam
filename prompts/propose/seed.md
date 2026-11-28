You are proposing a brand-new, realistic twin feature idea for `pallets/click`.

Target behaviour family: `{family}`
Family definition: {family_desc}

Click surface map:
{surface}

Features to AVOID (already used or rejected):
{avoid_list}

Requirements for your proposal:
1. Propose ONE cohesive, realistic feature that fits `click`'s design and does NOT already exist in `click`.
2. Identify ONE policy dimension inside this feature where two reasonable, opposing rules exist (`policy_a` and `policy_b`), each with a realistic stakeholder reason (`reason_a` and `reason_b`).
3. The difference between `policy_a` and `policy_b` MUST be observable through command-line behaviour (exit code, which value wins, which values are reported, or callback order), NEVER just error message wording.
4. `pair_id` must start with `{family}-` followed by a short lowercase kebab-case slug.

Reply with JSON only:
{{
  "pair_id": "{family}-<slug>",
  "family": "{family}",
  "feature": "<one clear paragraph describing the shared feature>",
  "policy_a": "<rule A>",
  "policy_b": "<rule B>",
  "reason_a": "<why a real team wants rule A>",
  "reason_b": "<why a real team wants rule B>"
}}

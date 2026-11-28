"""Twin feature seed proposal. Owner: Akshat."""
from __future__ import annotations

from factory.llm import llm_json, load_prompt
from factory.schema import Seed

FAMILY_DEFINITIONS: dict[str, str] = {
    "conflict": "Two options or parameters cannot be combined or interact when both are provided.",
    "precedence": "Multiple sources (CLI flags, env vars, default_map, defaults) compete for one value.",
    "repetition": "An option or flag is passed multiple times on the command line.",
    "validation": "Constraints on parameter values, types, ranges, or cross-parameter invariants.",
    "lifecycle": "Ordering or execution of callbacks, context setup/teardown, or chained group subcommands.",
    "deprecation": "Handling deprecated options, commands, or aliases (warnings vs errors vs fallback).",
    "retry": "Re-prompting or retrying failed interactive input or command execution.",
}


def propose_seed(surface: str, family: str, avoid: list[str]) -> Seed:
    """Propose a novel twin feature seed for the given behaviour family."""
    if family not in FAMILY_DEFINITIONS:
        raise ValueError(f"unknown family {family!r}; expected one of {sorted(FAMILY_DEFINITIONS)}")
    avoid_list = "\n".join(f"- {item}" for item in avoid) if avoid else "- (none)"
    prompt = load_prompt(
        "propose",
        "seed",
        family=family,
        family_desc=FAMILY_DEFINITIONS[family],
        surface=surface,
        avoid_list=avoid_list,
    )
    data = llm_json(prompt, role="seed")
    pair_id = str(data.get("pair_id", "")).strip()
    if not pair_id.startswith(f"{family}-"):
        slug = pair_id.lstrip("-") or "feature"
        pair_id = f"{family}-{slug}"
    seed = Seed(
        pair_id=pair_id,
        family=family,
        feature=str(data["feature"]).strip(),
        policy_a=str(data["policy_a"]).strip(),
        policy_b=str(data["policy_b"]).strip(),
        reason_a=str(data["reason_a"]).strip(),
        reason_b=str(data["reason_b"]).strip(),
    )
    if not all([seed.feature, seed.policy_a, seed.policy_b, seed.reason_a, seed.reason_b]):
        raise ValueError("seed fields must all be non-empty")
    return seed

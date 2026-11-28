"""Gate G9: realism rubric check for a proposed seed. Owner: Akshat."""
from __future__ import annotations

from factory.llm import llm_json, load_prompt
from factory.schema import GateResult, Seed


def realism_gate(seed: Seed, surface: str) -> GateResult:
    """Return GateResult(gate='G9', ...) scoring click-design fit, reason, and usefulness."""
    prompt = load_prompt(
        "propose",
        "realism",
        feature=seed.feature,
        policy_a=seed.policy_a,
        policy_b=seed.policy_b,
        reason_a=seed.reason_a,
        reason_b=seed.reason_b,
        surface=surface,
    )
    scores = llm_json(prompt, role="realism", pair_id=seed.pair_id)
    fit = int(scores["fit"])
    reason = int(scores["reason"])
    usefulness = int(scores["usefulness"])
    mean = (fit + reason + usefulness) / 3.0
    return GateResult(
        gate="G9",
        passed=mean >= 4.0,
        detail={
            "fit": fit,
            "reason": reason,
            "usefulness": usefulness,
            "mean": round(mean, 2),
            "comment": str(scores.get("comment", "")),
            "needs_human_signoff": True,
        },
    )

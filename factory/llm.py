"""The only door to a model. Owner: Dhrumil.

Every call is cached (for offline replay), costed (runs/costs.jsonl) and
capped per pair (FACTORY_PAIR_BUDGET_USD). FACTORY_OFFLINE=1 serves from the
cache only and never reaches a provider.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"
DEFAULT_MODEL = "claude-opus-5-5"

# USD per 1M tokens (input, output). Unknown models are priced as the default
# (the most expensive listed) so the budget cap errs on the safe side.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class OfflineCacheMiss(RuntimeError):
    pass


class BudgetExceeded(RuntimeError):
    pass


def _runs() -> Path:
    return Path(os.environ.get("FACTORY_RUNS", "runs"))


def _usd(model: str, in_tokens: int, out_tokens: int) -> float:
    pin, pout = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return (in_tokens * pin + out_tokens * pout) / 1_000_000


def _spent(pair_id: str) -> float:
    path = _runs() / "costs.jsonl"
    if not path.exists():
        return 0.0
    rows = (json.loads(line) for line in path.read_text().splitlines() if line)
    return sum(r["usd"] for r in rows if r["pair_id"] == pair_id)


def _call(prompt: str, model: str) -> tuple[str, int, int]:
    """Provider call. Returns (text, input_tokens, output_tokens)."""
    provider = os.environ.get("FACTORY_PROVIDER", "anthropic")
    if provider != "anthropic":
        raise NotImplementedError(f"provider {provider!r} not wired yet; add it here only")
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ.get("FACTORY_API_KEY") or None)
    # Current models reject temperature/top_p, so none are sent. Server-side
    # fallback re-runs a refused request on a fallback model in the same call.
    resp = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": prompt}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {getattr(resp.stop_details, 'category', None)}")
    text = "".join(b.text for b in resp.content if b.type == "text")
    return text, resp.usage.input_tokens, resp.usage.output_tokens


def llm(prompt: str, *, role: str, model: str | None = None, pair_id: str | None = None,
        temperature: float = 0.0) -> str:
    """`temperature` only separates cache entries; it is never sent to the provider."""
    model = model or os.environ.get("FACTORY_MODEL_DEFAULT", DEFAULT_MODEL)
    key = hashlib.sha256(f"{model}\n{temperature}\n{prompt}".encode()).hexdigest()
    cached = _runs() / "llm_cache" / f"{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())["text"]
    if os.environ.get("FACTORY_OFFLINE") == "1":
        raise OfflineCacheMiss(f"no cached response for role={role!r} pair={pair_id!r} model={model!r}")

    budget = float(os.environ.get("FACTORY_PAIR_BUDGET_USD", "5"))
    if pair_id is not None and _spent(pair_id) >= budget:
        raise BudgetExceeded(f"pair {pair_id!r} reached ${budget:.2f}")

    text, tin, tout = _call(prompt, model)
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps({"model": model, "role": role, "text": text}))
    with (_runs() / "costs.jsonl").open("a") as f:
        f.write(json.dumps({"ts": time.time(), "role": role, "model": model, "pair_id": pair_id,
                            "in_tokens": tin, "out_tokens": tout, "usd": _usd(model, tin, tout)}) + "\n")
    return text


def _parse_json(text: str):
    m = re.search(r"```(?:json)?\s*\n(.*?)```", text, re.S)
    return json.loads(m.group(1) if m else text)


def llm_json(prompt: str, *, role: str, model: str | None = None, pair_id: str | None = None):
    text = llm(prompt, role=role, model=model, pair_id=pair_id)
    try:
        return _parse_json(text)
    except json.JSONDecodeError as e:
        retry = f"{prompt}\n\nYour previous reply was not valid JSON ({e}). Reply with JSON only."
        return _parse_json(llm(retry, role=role, model=model, pair_id=pair_id))


def load_prompt(area: str, name: str, **vars) -> str:
    return (PROMPTS / area / f"{name}.md").read_text().format_map(vars)

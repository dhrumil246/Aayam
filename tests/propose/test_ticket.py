"""Unit tests for Markdown ticket rendering."""
import copy
from pathlib import Path

from factory.propose.ticket import render_ticket
from factory.schema import Contract, Seed, load

GOLDEN = Path(__file__).resolve().parents[2] / "fixtures" / "golden"


def test_ticket_hides_twin():
    seed = load(Seed, GOLDEN / "seed.json")
    a = load(Contract, GOLDEN / "contract_A.json")
    b = load(Contract, GOLDEN / "contract_B.json")
    rendered = render_ticket(a, seed)
    assert seed.pair_id not in rendered
    assert "twin" not in rendered.lower()
    assert b.pivot().text not in rendered


def test_ticket_open_items_section():
    seed = load(Seed, GOLDEN / "seed.json")
    a = load(Contract, GOLDEN / "contract_A.json")
    rendered = render_ticket(a, seed)
    assert "## Left to you" in rendered
    for item in a.open_items:
        assert item in rendered

    a_empty = copy.deepcopy(a)
    a_empty.open_items = []
    rendered_empty = render_ticket(a_empty, seed)
    assert "## Left to you" in rendered_empty
    assert "Nothing is left open" in rendered_empty


def test_ticket_golden_snapshot():
    seed = load(Seed, GOLDEN / "seed.json")
    a = load(Contract, GOLDEN / "contract_A.json")
    b = load(Contract, GOLDEN / "contract_B.json")
    assert render_ticket(a, seed) == (GOLDEN / "ticket_A.md").read_text(encoding="utf-8")
    assert render_ticket(b, seed) == (GOLDEN / "ticket_B.md").read_text(encoding="utf-8")

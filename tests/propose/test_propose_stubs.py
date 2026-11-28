"""Verify all factory.propose stage stubs exist with the signatures pipeline.py expects."""
import inspect

from factory.propose import contract, novelty, realism, reference, seeds, surface, ticket


def test_propose_stage_signatures():
    assert list(inspect.signature(surface.discover_surface).parameters) == ["pin"]
    assert list(inspect.signature(seeds.propose_seed).parameters) == ["surface", "family", "avoid"]
    assert list(inspect.signature(novelty.novelty_gate).parameters) == ["seed"]
    assert list(inspect.signature(realism.realism_gate).parameters) == ["seed", "surface"]
    assert list(inspect.signature(contract.write_contracts).parameters) == ["seed", "surface"]
    assert list(inspect.signature(contract.validate_contracts).parameters) == ["a", "b"]
    assert list(inspect.signature(ticket.render_ticket).parameters) == ["contract", "seed"]
    assert list(inspect.signature(reference.write_reference).parameters) == ["contract", "ticket", "pin", "out"]
    assert list(inspect.signature(reference.repair_reference).parameters) == [
        "contract",
        "ticket",
        "pin",
        "patch",
        "failure",
    ]

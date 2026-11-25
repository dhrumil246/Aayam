from factory.schema import Assertion, Contract, Finding, Invocation, Outcome, Pair, RepoPin, Requirement, Seed, load, save


def test_schema_roundtrip(tmp_path):
    inv = Invocation(["--json", "--yaml"], env={"APP_FORMAT": "json"})
    c = Contract("p", "A", "conflict", [Requirement("R1", "x"), Requirement("R2", "y", pivot=True)],
                 ["wording"], "api", "src", {"options": []}, inv)
    pair = Pair(Seed("p", "conflict", "f", "a", "b", "ra", "rb"), RepoPin("pallets/click", "8.2.1", "s"),
                contracts={"A": c}, expectations={"A": [Assertion("R2", "d", "outcome.exit_code == 2")]},
                findings=[Finding(inv, Outcome(2, "e"), Outcome(0, "ok", None))])
    save(pair, tmp_path / "pair.json")
    back = load(Pair, tmp_path / "pair.json")
    assert back == pair
    assert back.contracts["A"].pivot().id == "R2"

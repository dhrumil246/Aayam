import click


def test_new__R1__probe_returns_42():
    assert click.factory_probe() == 42


def test_preserved__R2__echo_still_exists():
    assert callable(click.echo)

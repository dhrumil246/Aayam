import pytest


def test_new__R1__skipped():
    pytest.skip("not graded")


@pytest.mark.xfail(reason="always xfail")
def test_new__R1__xfailed():
    assert False


@pytest.mark.xfail(reason="xpass")
def test_new__R1__xpassed():
    assert True


def test_preserved__R2__runs():
    assert True

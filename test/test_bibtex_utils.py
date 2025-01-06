from bibtex_utils import get_all_cites_in_dir


def test_get_all_cites_in_dir():
    cites = get_all_cites_in_dir("test/resources")
    assert cites == {
        "gruber2021empirical",
        "bazelAttributeFlaky",
        "lam2019idflakies",
        "wong2016survey",
    }

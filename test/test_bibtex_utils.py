from bibtex_utils import get_all_cites_in_dir


def test_get_all_cites_in_dir():
    cites = get_all_cites_in_dir("test/resources")
    assert cites == {"gruber2021empirical", "bell2018deflaker", "lam2019idflakies"}

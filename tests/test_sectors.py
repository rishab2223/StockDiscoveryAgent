from sda.sectors import GICS_SECTORS, normalize_sector


def test_yahoo_labels_map_onto_gics():
    assert normalize_sector("Technology") == "Information Technology"
    assert normalize_sector("Healthcare") == "Health Care"
    assert normalize_sector("Financial Services") == "Financials"
    assert normalize_sector("Consumer Cyclical") == "Consumer Discretionary"
    assert normalize_sector("Consumer Defensive") == "Consumer Staples"
    assert normalize_sector("Basic Materials") == "Materials"


def test_gics_names_and_unknowns_pass_through():
    for name in GICS_SECTORS:
        assert normalize_sector(name) == name
        assert normalize_sector(name.lower()) == name
    assert normalize_sector(None) == "Unknown" and normalize_sector("  ") == "Unknown"
    assert normalize_sector(" Shipping ") == "Shipping"

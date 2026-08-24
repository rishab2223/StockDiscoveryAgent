from sda.news.filter import classify_rule, filter_news, mentions_company


def test_drops_analyst_and_keeps_earnings():
    drop = {
        "ticker": "AAPL",
        "title": "Morgan Stanley upgrades AAPL, raises price target",
        "summary": "Analysts lift rating to overweight",
        "publisher": "Street",
    }
    keep = {
        "ticker": "AAPL",
        "title": "Apple announces quarterly earnings and raises guidance",
        "summary": "Press release on revenue and outlook",
        "publisher": "Business Wire",
    }
    assert classify_rule(drop) == "drop"
    assert classify_rule(keep) == "keep"
    split = filter_news([drop, keep, keep])
    assert len(split["keep"]) == 1
    assert len(split["drop"]) == 1
    fool = {
        "ticker": "AMZN",
        "title": "If Amazon Is a Top Growth Stock, Then Why Does It Trade Cheap?",
        "summary": "This is the only answer I can think of.",
        "publisher": "Motley Fool",
    }
    assert classify_rule(fool) == "drop"
    nvda_on_amzn = {
        "ticker": "AMZN",
        "title": "Nvidia's Q2 earnings to test resurgent AI trade",
        "summary": "Nvidia will report its Q2 earnings after the bell.",
        "publisher": "Yahoo Finance",
    }
    assert mentions_company(nvda_on_amzn, "AMZN", "Amazon.com, Inc.") is False
    assert mentions_company(keep, "AAPL", "Apple Inc.") is True

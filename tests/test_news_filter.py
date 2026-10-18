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
    split = filter_news([drop, keep, {**keep, "title": keep["title"].upper()}])
    assert len(split["keep"]) == 1  # duplicate title (case-insensitive) dropped
    assert len(split["drop"]) == 1
    assert split["keep"][0]["rule_label"] == "keep"


def test_ambiguous_and_opinion_publishers():
    fool = {
        "ticker": "AMZN",
        "title": "If Amazon Is a Top Growth Stock, Then Why Does It Trade Cheap?",
        "summary": "This is the only answer I can think of.",
        "publisher": "Motley Fool",
    }
    assert classify_rule(fool) == "drop"
    assert classify_rule({"title": "Axon announces contract wins", "publisher": "Simply Wall St."}) == "drop"
    both ={"ticker": "X", "title": "Analysts react as X announces earnings", "publisher": "Reuters"}
    assert classify_rule(both) == "maybe"
    neither = {"ticker": "X", "title": "X shares rise", "publisher": "Reuters"}
    assert classify_rule(neither) == "maybe"


def test_related_tickers_decide_when_present():
    item = {"title": "Nvidia's Q2 earnings", "related_tickers": ["NVDA", "AMD"]}
    assert mentions_company(item, "NVDA") is True
    assert mentions_company(item, "AMZN", "Amazon.com, Inc.") is False
    assert mentions_company({**item, "related_tickers": ["brk-b"]}, "BRK-B") is True


def test_text_fallback_uses_symbol_or_name_word():
    nvda_on_amzn = {
        "ticker": "AMZN",
        "title": "Nvidia's Q2 earnings to test resurgent AI trade",
        "summary": "Nvidia will report its Q2 earnings after the bell.",
        "publisher": "Yahoo Finance",
    }
    assert mentions_company(nvda_on_amzn, "AMZN", "Amazon.com, Inc.") is False
    keep = {"title": "Apple announces quarterly earnings", "summary": "", "publisher": "Business Wire"}
    assert mentions_company(keep, "AAPL", "Apple Inc.") is True
    assert mentions_company({"title": "Pineapple harvest beats estimates"}, "AAPL", "Apple Inc.") is False
    assert mentions_company({"title": "Shares of AAPL jump"}, "AAPL") is True


def test_short_and_wordlike_symbols_do_not_leak():
    airline = {"title": "GOL cancels all U.S. flights", "summary": "All routes suspended."}
    assert mentions_company(airline, "ALL", "Allstate Corporation") is False
    assert mentions_company({"title": "Allstate raises guidance"}, "ALL", "Allstate Corporation") is True
    assert mentions_company({"title": "Ford (F) recalls trucks"}, "F", "Ford Motor Company") is True
    assert mentions_company({"title": "$T slides after earnings"}, "T", "AT&T Inc.") is True
    assert mentions_company({"title": "Don't forget to vote"}, "T", "AT&T Inc.") is False
    assert mentions_company({"title": "The cat sat on the mat"}, "CAT", "Caterpillar Inc.") is False

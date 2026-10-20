from app.market_data.symbols import classify_and_normalize


def test_classify_crypto():
    sym, asset_type = classify_and_normalize("btcusdt")
    assert sym == "BTCUSDT"
    assert asset_type == "CRYPTO"

    sym2, asset_type2 = classify_and_normalize("ETHFDUSD")
    assert sym2 == "ETHFDUSD"
    assert asset_type2 == "CRYPTO"


def test_classify_bist():
    sym, asset_type = classify_and_normalize("THYAO")
    assert sym == "THYAO.IS"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("asels.is")
    assert sym2 == "ASELS.IS"
    assert asset_type2 == "EQUITY_FOREX"


def test_classify_forex():
    sym, asset_type = classify_and_normalize("usdtry")
    assert sym == "USDTRY=X"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("EURUSD=X")
    assert sym2 == "EURUSD=X"
    assert asset_type2 == "EQUITY_FOREX"


def test_classify_commodities():
    sym, asset_type = classify_and_normalize("gold")
    assert sym == "GC=F"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("altin")
    assert sym2 == "GC=F"
    assert asset_type2 == "EQUITY_FOREX"

    sym3, asset_type3 = classify_and_normalize("brent")
    assert sym3 == "BZ=F"
    assert asset_type3 == "EQUITY_FOREX"


def test_classify_us_equities():
    sym, asset_type = classify_and_normalize("aapl")
    assert sym == "AAPL"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("NVDA")
    assert sym2 == "NVDA"
    assert asset_type2 == "EQUITY_FOREX"

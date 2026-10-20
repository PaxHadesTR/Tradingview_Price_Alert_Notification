from app.market_data.symbols import classify_and_normalize, get_symbol_autocomplete


def test_classify_crypto():
    sym, asset_type = classify_and_normalize("btcusdt")
    assert sym == "BTCUSDT"
    assert asset_type == "CRYPTO"

    sym2, asset_type2 = classify_and_normalize("ETHFDUSD")
    assert sym2 == "ETHFDUSD"
    assert asset_type2 == "CRYPTO"


def test_classify_crypto_shorthand():
    sym, asset_type = classify_and_normalize("btc")
    assert sym == "BTCUSDT"
    assert asset_type == "CRYPTO"

    sym2, asset_type2 = classify_and_normalize("eth")
    assert sym2 == "ETHUSDT"
    assert asset_type2 == "CRYPTO"

    sym3, asset_type3 = classify_and_normalize("sol")
    assert sym3 == "SOLUSDT"
    assert asset_type3 == "CRYPTO"

    sym4, asset_type4 = classify_and_normalize("sui")
    assert sym4 == "SUIUSDT"
    assert asset_type4 == "CRYPTO"

    sym5, asset_type5 = classify_and_normalize("pepe")
    assert sym5 == "PEPEUSDT"
    assert asset_type5 == "CRYPTO"


def test_classify_indices():
    sym, asset_type = classify_and_normalize("nasdaq")
    assert sym == "^NDX"
    assert asset_type == "EQUITY_FOREX"

    sym_nq, _ = classify_and_normalize("nq")
    assert sym_nq == "NQ=F"

    sym_dji, _ = classify_and_normalize("dji")
    assert sym_dji == "^DJI"

    sym_dow, _ = classify_and_normalize("dow")
    assert sym_dow == "^DJI"

    sym_us30, _ = classify_and_normalize("us30")
    assert sym_us30 == "^DJI"

    sym2, asset_type2 = classify_and_normalize("xu100")
    assert sym2 == "XU100.IS"
    assert asset_type2 == "EQUITY_FOREX"

    sym3, asset_type3 = classify_and_normalize("bist100")
    assert sym3 == "XU100.IS"
    assert asset_type3 == "EQUITY_FOREX"

    sym4, asset_type4 = classify_and_normalize("dxy")
    assert sym4 == "DX-Y.NYB"
    assert asset_type4 == "EQUITY_FOREX"

    sym5, asset_type5 = classify_and_normalize("sp500")
    assert sym5 == "^GSPC"
    assert asset_type5 == "EQUITY_FOREX"


def test_classify_bist():
    sym, asset_type = classify_and_normalize("THYAO")
    assert sym == "THYAO.IS"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("asels.is")
    assert sym2 == "ASELS.IS"
    assert asset_type2 == "EQUITY_FOREX"

    sym3, asset_type3 = classify_and_normalize("mavi")
    assert sym3 == "MAVI.IS"
    assert asset_type3 == "EQUITY_FOREX"

    sym4, asset_type4 = classify_and_normalize("enjsa")
    assert sym4 == "ENJSA.IS"
    assert asset_type4 == "EQUITY_FOREX"


def test_classify_forex():
    sym, asset_type = classify_and_normalize("usdtry")
    assert sym == "USDTRY=X"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("EURUSD=X")
    assert sym2 == "EURUSD=X"
    assert asset_type2 == "EQUITY_FOREX"

    sym3, asset_type3 = classify_and_normalize("gbptry")
    assert sym3 == "GBPTRY=X"
    assert asset_type3 == "EQUITY_FOREX"


def test_classify_commodities():
    sym, asset_type = classify_and_normalize("gold")
    assert sym == "GC=F"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("xau")
    assert sym2 == "GC=F"
    assert asset_type2 == "EQUITY_FOREX"

    sym3, asset_type3 = classify_and_normalize("xauusd")
    assert sym3 == "GC=F"
    assert asset_type3 == "EQUITY_FOREX"

    sym4, asset_type4 = classify_and_normalize("brent")
    assert sym4 == "BZ=F"
    assert asset_type4 == "EQUITY_FOREX"

    sym5, asset_type5 = classify_and_normalize("wti")
    assert sym5 == "CL=F"
    assert asset_type5 == "EQUITY_FOREX"

    sym6, asset_type6 = classify_and_normalize("silver")
    assert sym6 == "SI=F"
    assert asset_type6 == "EQUITY_FOREX"


def test_classify_us_equities():
    sym, asset_type = classify_and_normalize("aapl")
    assert sym == "AAPL"
    assert asset_type == "EQUITY_FOREX"

    sym2, asset_type2 = classify_and_normalize("NVDA")
    assert sym2 == "NVDA"
    assert asset_type2 == "EQUITY_FOREX"

    sym3, asset_type3 = classify_and_normalize("tsla")
    assert sym3 == "TSLA"
    assert asset_type3 == "EQUITY_FOREX"


def test_autocomplete():
    # Empty query returns top presets (up to 25)
    default_res = get_symbol_autocomplete("")
    assert len(default_res) == 25

    # Specific crypto query
    btc_res = get_symbol_autocomplete("btc")
    assert any("BTC" in label for label, _ in btc_res)

    # Specific BIST query
    thyao_res = get_symbol_autocomplete("thyao")
    assert any("THYAO" in val for _, val in thyao_res)

    # Specific index query
    nasdaq_res = get_symbol_autocomplete("nasdaq")
    assert any("NASDAQ" in val for _, val in nasdaq_res)

    # Custom ticker not in presets returns Custom ticker as 1st option
    custom_res = get_symbol_autocomplete("CUSTOMTICKER123")
    assert custom_res[0][1] == "CUSTOMTICKER123"

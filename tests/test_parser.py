import json
from app.services.parser import parse_tradingview_payload


def test_parse_structured_json():
    raw = json.dumps({
        "passphrase": "secret_abc",
        "ticker": "BTCUSDT",
        "action": "BUY",
        "price": 68500.25,
        "strategy": "EMA Crossover",
        "timeframe": "15m",
        "message": "Strong buy signal generated",
        "custom_metric": 42.5,
    })
    alert = parse_tradingview_payload(raw)

    assert alert.passphrase == "secret_abc"
    assert alert.ticker == "BTCUSDT"
    assert alert.action == "BUY"
    assert alert.price == 68500.25
    assert alert.strategy == "EMA Crossover"
    assert alert.timeframe == "15m"
    assert alert.message == "Strong buy signal generated"
    assert alert.extra_data.get("custom_metric") == 42.5
    assert alert.is_bullish is True
    assert alert.is_bearish is False
    assert alert.embed_color == 0x00FF88


def test_parse_tradingview_aliases():
    raw = json.dumps({
        "symbol": "ETHUSD",
        "side": "sell",
        "close": "3450.75",
        "interval": "1h",
        "indicator": "RSI Divergence",
    })
    alert = parse_tradingview_payload(raw)

    assert alert.ticker == "ETHUSD"
    assert alert.action == "SELL"
    assert alert.price == 3450.75
    assert alert.timeframe == "1h"
    assert alert.strategy == "RSI Divergence"
    assert alert.is_bearish is True
    assert alert.is_bullish is False
    assert alert.embed_color == 0xFF3366


def test_parse_key_value_plain_text():
    raw = "ticker=SOLUSDT action=SHORT price=185.20 strategy=BollingerBreak"
    alert = parse_tradingview_payload(raw)

    assert alert.ticker == "SOLUSDT"
    assert alert.action == "SHORT"
    assert alert.price == 185.20
    assert alert.strategy == "BollingerBreak"
    assert alert.is_bearish is True


def test_parse_simple_token_text():
    raw = "AVAXUSDT BUY @ 32.50 Target reached"
    alert = parse_tradingview_payload(raw)

    assert alert.ticker == "AVAXUSDT"
    assert alert.action == "BUY"
    assert alert.price == 32.50
    assert "Target reached" in (alert.message or "")


def test_parse_malformed_fallback():
    raw = "THIS IS NOT JSON OR A STANDARD FORMAT !!!"
    alert = parse_tradingview_payload(raw)

    assert alert.ticker == "TRADINGVIEW"
    assert alert.action == "ALERT"
    assert alert.message == raw
    assert alert.is_bullish is False
    assert alert.is_bearish is False
    assert alert.embed_color == 0x3399FF


def test_parse_empty_string():
    alert = parse_tradingview_payload("   ")
    assert alert.ticker == "EMPTY_ALERT"


def test_parse_bytes_input():
    raw = b'{"ticker": "XRPUSDT", "action": "BUY", "price": 0.55}'
    alert = parse_tradingview_payload(raw)
    assert alert.ticker == "XRPUSDT"
    assert alert.action == "BUY"
    assert alert.price == 0.55

import json
import logging
import re
from typing import Any, Dict, Optional, Tuple, Union
from app.models.alert import AlertPayload

logger = logging.getLogger(__name__)


def parse_tradingview_payload(raw_body: Union[str, bytes, dict]) -> AlertPayload:
    """Robust dual-parser: translates JSON, key-value text, or raw string into normalized AlertPayload.

    Never raises unhandled parsing exceptions; falls back gracefully to a generic AlertPayload
    to ensure alerts are never dropped.
    """
    if isinstance(raw_body, bytes):
        try:
            raw_body = raw_body.decode("utf-8").strip()
        except UnicodeDecodeError:
            raw_body = raw_body.decode("latin1", errors="replace").strip()

    if isinstance(raw_body, dict):
        return _from_dict(raw_body)

    if not isinstance(raw_body, str):
        return AlertPayload(ticker="UNKNOWN", message=str(raw_body))

    text = raw_body.strip()
    if not text:
        return AlertPayload(ticker="EMPTY_ALERT", message="Received empty alert payload.")

    # Strip markdown code blocks if payload is enclosed in ``` or ```json
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            text = "\n".join(lines[1:-1]).strip()

    # 1. Attempt JSON parsing
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return _from_dict(data)
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                return _from_dict(data[0])
        except Exception as e:
            logger.debug("Failed parsing text as JSON: %s", e)

    # 2. Attempt Key-Value text parsing (e.g. ticker=BTCUSDT action=BUY price=65000)
    kv_data = _extract_key_values(text)
    if kv_data.get("ticker") or kv_data.get("action") or kv_data.get("price"):
        return _from_dict(kv_data)

    # 3. Attempt simple regex token extraction (e.g. "BTCUSDT BUY 68500.50 EMA Cross")
    extracted = _extract_tokens_from_plain_text(text)
    if extracted:
        return extracted

    # 4. Ultimate Fallback: Preserves complete payload message
    return AlertPayload(
        ticker="TRADINGVIEW",
        action="ALERT",
        message=text,
    )


def _from_dict(data: Dict[str, Any]) -> AlertPayload:
    """Normalize dictionary mapping common TradingView aliases to standard AlertPayload fields."""
    # Field Aliases
    ticker = (
        data.get("ticker")
        or data.get("symbol")
        or data.get("pair")
        or data.get("instrument")
        or "UNKNOWN"
    )

    action = (
        data.get("action")
        or data.get("side")
        or data.get("signal")
        or data.get("order")
        or "ALERT"
    )

    price_val = (
        data.get("price")
        or data.get("close")
        or data.get("rate")
        or data.get("entry")
    )
    price: Optional[float] = None
    if price_val is not None:
        if isinstance(price_val, (int, float)):
            price = float(price_val)
        else:
            try:
                s = str(price_val).strip()
                s = re.sub(r"[^\d\.,\-]", "", s)
                if "," in s and "." in s:
                    s = s.replace(",", "")
                elif "," in s and "." not in s:
                    s = s.replace(",", ".")
                price = float(s)
            except (ValueError, TypeError):
                price = None

    strategy = (
        data.get("strategy")
        or data.get("indicator")
        or data.get("condition")
        or data.get("alert_name")
    )

    timeframe = (
        data.get("timeframe")
        or data.get("interval")
        or data.get("tf")
        or data.get("resolution")
    )

    message = (
        data.get("message")
        or data.get("msg")
        or data.get("text")
        or data.get("comment")
    )

    passphrase = (
        data.get("passphrase")
        or data.get("secret")
        or data.get("token")
        or data.get("auth")
    )

    # Filter out known standard fields to isolate extra custom data
    known_keys = {
        "ticker", "symbol", "pair", "instrument",
        "action", "side", "signal", "order",
        "price", "close", "rate", "entry",
        "strategy", "indicator", "condition", "alert_name",
        "timeframe", "interval", "tf", "resolution",
        "message", "msg", "text", "comment",
        "passphrase", "secret", "token", "auth",
    }
    extra_data = {k: v for k, v in data.items() if k not in known_keys}

    return AlertPayload(
        passphrase=str(passphrase) if passphrase is not None else None,
        ticker=str(ticker).strip().upper(),
        action=str(action).strip().upper(),
        price=price,
        strategy=str(strategy).strip() if strategy else None,
        timeframe=str(timeframe).strip() if timeframe else None,
        message=str(message).strip() if message else None,
        extra_data=extra_data,
    )


def _extract_key_values(text: str) -> Dict[str, Any]:
    """Parse string formatted as key=value or key: value, handling whitespace/comma separators and quotes."""
    result: Dict[str, Any] = {}
    pattern = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)\s*[:=]\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s,;]+))")
    for match in pattern.finditer(text):
        key = match.group(1).lower().strip()
        val = match.group(2) if match.group(2) is not None else (
            match.group(3) if match.group(3) is not None else match.group(4)
        )
        if val is not None:
            result[key] = val.strip()
    return result


def _extract_tokens_from_plain_text(text: str) -> Optional[AlertPayload]:
    """Extract standard pattern like `BTCUSDT BUY 65000` or `ETH/USD SELL @ 3400,20`."""
    pattern = re.compile(
        r"^([A-Z0-9_\-\.\/]{2,15})\s+(BUY|SELL|LONG|SHORT|CLOSE|ALERT)\b(?:\s+(?:@\s*)?([0-9]+(?:[\.,][0-9]+)?))?(.*)$",
        re.IGNORECASE,
    )
    match = pattern.match(text)
    if not match:
        return None

    ticker = match.group(1).upper()
    action = match.group(2).upper()
    price_str = match.group(3)
    price: Optional[float] = None
    if price_str:
        try:
            price = float(price_str.replace(",", "."))
        except ValueError:
            price = None
    remaining_msg = match.group(4).strip() if match.group(4) else None

    return AlertPayload(
        ticker=ticker,
        action=action,
        price=price,
        message=remaining_msg or text,
    )

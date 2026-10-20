import re
from typing import Tuple

# Common Turkish BIST stocks list for convenient auto-suffixing
BIST_POPULAR = {
    "THYAO", "ASELS", "GARAN", "EREGL", "SISE", "KCHOL", "AKBNK", "BIMAS", "TUPRS",
    "YKBNK", "SAHOL", "FROTO", "TOASO", "PETKM", "KOZAL", "PGSUS", "TCELL", "TTKOM",
    "ENKAI", "ARCLK", "VESTL", "HEKTS", "SASA", "GUBRF", "KOZAA", "SOKM", "MGROS",
    "ISCTR", "VAKBN", "HALKB", "EKGYO", "ASTOR", "KONTR", "ALARK", "ODAS", "CANTE"
}

# Currency / Forex pairs for auto-suffixing with =X
FOREX_PAIRS = {
    "USDTRY", "EURTRY", "EURUSD", "GBPUSD", "USDJPY", "GBPTRY", "USDCHF", "AUDUSD"
}

# Commodity aliases mapping to Yahoo Finance futures
COMMODITY_MAP = {
    "GOLD": "GC=F",
    "ALTIN": "GC=F",
    "XAUUSD": "GC=F",
    "ONS": "GC=F",
    "SILVER": "SI=F",
    "GUMUS": "SI=F",
    "XAGUSD": "SI=F",
    "BRENT": "BZ=F",
    "PETROL": "BZ=F",
    "CRUDE": "CL=F",
}


def classify_and_normalize(raw_symbol: str) -> Tuple[str, str]:
    """Normalize input symbol and determine whether it routes to Binance WS or Yahoo Finance.

    :param raw_symbol: User inputted symbol (e.g., btcusdt, THYAO, USDTRY, AAPL, GOLD)
    :return: (normalized_symbol, asset_type) where asset_type is 'CRYPTO' or 'EQUITY_FOREX'
    """
    clean = raw_symbol.strip().upper()

    # Strip prefixes like BINANCE: or BIST:
    if ":" in clean:
        prefix, clean = clean.split(":", 1)

    # 1. Check Commodity aliases
    if clean in COMMODITY_MAP:
        return COMMODITY_MAP[clean], "EQUITY_FOREX"

    # 2. Check Forex pairs
    if clean in FOREX_PAIRS:
        return f"{clean}=X", "EQUITY_FOREX"
    if clean.endswith("=X"):
        return clean, "EQUITY_FOREX"

    # 3. Check BIST stocks
    if clean.endswith(".IS"):
        return clean, "EQUITY_FOREX"
    if clean in BIST_POPULAR:
        return f"{clean}.IS", "EQUITY_FOREX"

    # 4. Check Crypto patterns (e.g. BTCUSDT, ETHUSDT, SOLFDUSD, DOGEBTC)
    crypto_quote_currencies = ("USDT", "FDUSD", "USDC", "BTC", "ETH", "BNB")
    for quote in crypto_quote_currencies:
        if clean.endswith(quote) and len(clean) > len(quote):
            return clean, "CRYPTO"

    # 5. Check if it ends with .F, =F (futures) or is standard US stock
    if clean.endswith("=F"):
        return clean, "EQUITY_FOREX"

    # If it's a short letters-only string (e.g. AAPL, TSLA), treat as US equity on Yahoo
    if re.match(r"^[A-Z]{1,5}$", clean):
        # Default fallback to EQUITY_FOREX unless user intended crypto
        return clean, "EQUITY_FOREX"

    # Default to CRYPTO if unknown
    return clean, "CRYPTO"

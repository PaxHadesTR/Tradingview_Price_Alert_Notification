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

# Major Global & Local Indices
INDEX_MAP = {
    # Turkish BIST Indices
    "XU100": "XU100.IS",
    "BIST100": "XU100.IS",
    "BIST": "XU100.IS",
    "BORSA": "XU100.IS",
    "XU030": "XU030.IS",
    "BIST30": "XU030.IS",
    "XBANK": "XBANK.IS",
    "XUSIN": "XUSIN.IS",
    "XBLSM": "XBLSM.IS",
    "XGIDA": "XGIDA.IS",
    "XUTEK": "XUTEK.IS",

    # US & Global Major Indices
    "NASDAQ": "^IXIC",
    "NASDAQ100": "^NDX",
    "NDX": "^NDX",
    "IXIC": "^IXIC",
    "QQQ": "QQQ",
    "SP500": "^GSPC",
    "S&P500": "^GSPC",
    "SPX": "^GSPC",
    "DOW": "^DJI",
    "DJI": "^DJI",
    "DOWJONES": "^DJI",
    "DAX": "^GDAXI",
    "FTSE": "^FTSE",
    "NIKKEI": "^N225",

    # Dollar Index
    "DXY": "DX-Y.NYB",
    "DX-Y": "DX-Y.NYB",
    "USDX": "DX-Y.NYB",
}

# Commodity aliases mapping to Yahoo Finance futures
COMMODITY_MAP = {
    "GOLD": "GC=F",
    "ALTIN": "GC=F",
    "XAU": "GC=F",
    "XAUUSD": "GC=F",
    "ONS": "GC=F",
    "SILVER": "SI=F",
    "GUMUS": "SI=F",
    "XAG": "SI=F",
    "XAGUSD": "SI=F",
    "BRENT": "BZ=F",
    "PETROL": "BZ=F",
    "CRUDE": "CL=F",
    "OIL": "CL=F",
    "COPPER": "HG=F",
    "BAKIR": "HG=F",
    "NATGAS": "NG=F",
    "DOGALGAZ": "NG=F",
    "PLATINUM": "PL=F",
    "PLATIN": "PL=F",
}

# Crypto shorthand aliases (When users type just "BTC" instead of "BTCUSDT")
CRYPTO_SHORTHAND = {
    "BTC": "BTCUSDT",
    "BITCOIN": "BTCUSDT",
    "ETH": "ETHUSDT",
    "ETHEREUM": "ETHUSDT",
    "SOL": "SOLUSDT",
    "SOLANA": "SOLUSDT",
    "BNB": "BNBUSDT",
    "XRP": "XRPUSDT",
    "RIPPLE": "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "ADA": "ADAUSDT",
    "CARDANO": "ADAUSDT",
    "AVAX": "AVAXUSDT",
    "AVALANCHE": "AVAXUSDT",
    "DOT": "DOTUSDT",
    "POLKADOT": "DOTUSDT",
    "LINK": "LINKUSDT",
    "CHAINLINK": "LINKUSDT",
    "MATIC": "POLUSDT",
    "POL": "POLUSDT",
    "NEAR": "NEARUSDT",
    "SUI": "SUIUSDT",
    "PEPE": "PEPEUSDT",
    "SHIB": "SHIBUSDT",
    "APT": "APTUSDT",
    "TON": "TONUSDT",
}


def classify_and_normalize(raw_symbol: str) -> Tuple[str, str]:
    """Normalize input symbol and determine whether it routes to Binance WS or Yahoo Finance.

    :param raw_symbol: User inputted symbol (e.g., btcusdt, btc, NASDAQ, XU100, xau, THYAO, USDTRY)
    :return: (normalized_symbol, asset_type) where asset_type is 'CRYPTO' or 'EQUITY_FOREX'
    """
    clean = raw_symbol.strip().upper()

    # Strip prefixes like BINANCE: or BIST: or TV:
    if ":" in clean:
        prefix, clean = clean.split(":", 1)

    # 1. Check Major Indices (NASDAQ, XU100, BIST100, SP500, DXY, etc.)
    if clean in INDEX_MAP:
        return INDEX_MAP[clean], "EQUITY_FOREX"

    # 2. Check Commodity aliases (GOLD, ALTIN, XAU, XAUUSD, SILVER, XAG, BRENT, etc.)
    if clean in COMMODITY_MAP:
        return COMMODITY_MAP[clean], "EQUITY_FOREX"

    # 3. Check Crypto Shorthand (e.g. BTC -> BTCUSDT, ETH -> ETHUSDT)
    if clean in CRYPTO_SHORTHAND:
        return CRYPTO_SHORTHAND[clean], "CRYPTO"

    # 4. Check Forex pairs
    if clean in FOREX_PAIRS:
        return f"{clean}=X", "EQUITY_FOREX"
    if clean.endswith("=X"):
        return clean, "EQUITY_FOREX"

    # 5. Check BIST symbols or Turkish index prefixes
    if clean.endswith(".IS"):
        return clean, "EQUITY_FOREX"
    if clean.startswith("XU") or clean.startswith("XB") or clean in BIST_POPULAR:
        return f"{clean}.IS", "EQUITY_FOREX"

    # 6. Check Crypto patterns (e.g. BTCUSDT, ETHUSDT, SOLFDUSD, DOGEBTC)
    crypto_quote_currencies = ("USDT", "FDUSD", "USDC", "BTC", "ETH", "BNB")
    for quote in crypto_quote_currencies:
        if clean.endswith(quote) and len(clean) > len(quote):
            return clean, "CRYPTO"

    # 7. Check if it ends with .F, =F (futures) or index ^
    if clean.endswith("=F") or clean.startswith("^"):
        return clean, "EQUITY_FOREX"

    # Default fallback: Treat as EQUITY_FOREX (Yahoo Finance), supporting US stocks and BIST fallback
    return clean, "EQUITY_FOREX"


# Autocomplete suggestions list (Label, Value)
AUTOCOMPLETE_PRESETS = [
    ("BTCUSDT (Bitcoin)", "BTCUSDT"),
    ("ETHUSDT (Ethereum)", "ETHUSDT"),
    ("SOLUSDT (Solana)", "SOLUSDT"),
    ("PEPEUSDT (Pepe Coin)", "PEPEUSDT"),
    ("XRPUSDT (Ripple)", "XRPUSDT"),
    ("AVAXUSDT (Avalanche)", "AVAXUSDT"),
    ("DOGEUSDT (Dogecoin)", "DOGEUSDT"),
    ("XU100 (BIST 100 Endeksi)", "XU100"),
    ("XU030 (BIST 30 Endeksi)", "XU030"),
    ("THYAO (Türk Hava Yolları)", "THYAO"),
    ("ASELS (Aselsan)", "ASELS"),
    ("GARAN (Garanti Bankası)", "GARAN"),
    ("EREGL (Ereğli Demir Çelik)", "EREGL"),
    ("SISE (Şişecam)", "SISE"),
    ("TUPRS (Tüpraş)", "TUPRS"),
    ("KCHOL (Koç Holding)", "KCHOL"),
    ("GOLD / XAU (Ons Altın)", "GOLD"),
    ("SILVER / XAG (Gümüş)", "SILVER"),
    ("BRENT (Brent Petrol)", "BRENT"),
    ("NASDAQ (Nasdaq Endeksi)", "NASDAQ"),
    ("SP500 (S&P 500 Endeksi)", "SP500"),
    ("DXY (Dolar Endeksi)", "DXY"),
    ("USDTRY (Dolar / TL)", "USDTRY"),
    ("EURTRY (Euro / TL)", "EURTRY"),
    ("AAPL (Apple Inc.)", "AAPL"),
    ("NVDA (NVIDIA Corp.)", "NVDA"),
    ("TSLA (Tesla Inc.)", "TSLA"),
]


def get_symbol_autocomplete(current: str) -> list[tuple[str, str]]:
    """Return filtered autocomplete choices matching user input."""
    clean = current.strip().upper()
    if not clean:
        return AUTOCOMPLETE_PRESETS[:20]

    matches = []
    for label, val in AUTOCOMPLETE_PRESETS:
        if clean in val.upper() or clean in label.upper():
            matches.append((label, val))

    # If user typed a custom ticker not in presets, keep custom at the top
    if not any(val.upper() == clean for _, val in matches):
        matches.insert(0, (f"Özel: {clean}", clean))

    return matches[:25]

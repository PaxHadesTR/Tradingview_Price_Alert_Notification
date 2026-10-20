import re
from typing import Tuple

# ---------------------------------------------------------------------------
# Borsa Istanbul (BIST) Equities
# All symbols listed here automatically get .IS appended for Yahoo Finance.
# ---------------------------------------------------------------------------
BIST_POPULAR = {
    # BIST 30 & Large Caps
    "THYAO", "ASELS", "GARAN", "EREGL", "SISE", "KCHOL", "AKBNK", "BIMAS", "TUPRS",
    "YKBNK", "SAHOL", "FROTO", "TOASO", "PETKM", "KOZAL", "PGSUS", "TCELL", "TTKOM",
    "ENKAI", "ARCLK", "VESTL", "HEKTS", "SASA", "GUBRF", "KOZAA", "SOKM", "MGROS",
    "ISCTR", "VAKBN", "HALKB", "EKGYO", "ASTOR", "KONTR", "ALARK", "ODAS", "CANTE",

    # Banking & Financial Institutions
    "ALBRK", "SKBNK", "TSKB", "QNBFB", "KLNMA", "ANSGR", "AKGRT", "TURSG", "AGESA",
    "ISFIN", "VAKFN", "ISMEN", "OYAYO", "INFO", "GEDIK", "GLBMD", "OSMEN",

    # Holdings & Conglomerates
    "DOHOL", "AGHOL", "BERA", "GSDHO", "GLYHO", "TKFEN", "POLHO", "ALGYO", "ECZYT",
    "GSDDE", "HUBVC", "INVEO", "VERUS",

    # Energy, Renewable & Electricity
    "EUPWR", "CWENE", "ENJSA", "AKSEN", "ZOREN", "AKENR", "BIOEN", "GWIND", "YEOTK",
    "SAYAS", "GESAN", "ALFAS", "SMRTG", "MOGAN", "ENERY", "TATEN", "KOPOL", "CVKMD",
    "KAYSE", "ANGEN", "MAGEN", "AHGAZ", "HUNER", "CANTE", "CONSE", "AYDEM",

    # Technology, Software & Defense
    "REEDR", "MIATK", "SDTTR", "PAPIL", "ARDYZ", "VBTYZ", "FORTE", "PATEK", "BINHO",
    "ALVES", "AGROT", "MOBTL", "INDES", "LOGO", "KFEIN", "FONET", "DESPEC", "DATAGATE",
    "LINK", "KAREL", "NETAS", "OBAMS", "TABGD", "BIGCH",

    # Industrial, Steel & Manufacturing
    "BRSAN", "TAVHL", "CCOLA", "MAVI", "OTKAR", "KRDMD", "KRDMA", "KRDMB", "ISDMR",
    "CEMTS", "BMSCH", "TUCLK", "KCAER", "ERBOS", "SARKY", "TMSN", "ASUZU", "KARSN",
    "BRISA", "GOODY", "JANTS", "BFREN", "EGEEN", "VESBE", "KLMSN", "ARZUM",

    # Cement, Glass & Building Materials
    "OYAKC", "CIMSA", "AKCNS", "NUHCM", "BUCIM", "BTCIM", "QUAGR", "BOBET", "BNTAS",
    "EGSER", "KALEK",

    # Real Estate Investment Trusts (GYO)
    "ISGYO", "VKGYO", "TRGYO", "OZKGY", "SNGYO", "KLGYO", "PEKGY", "RYGYO", "HLGYO",
    "KGYO", "ASGYO", "SURGY", "KZBGY", "MHRGY", "AKFGY", "PSGYO", "YGYO", "DGGYO",

    # Pharma, Health & Chemicals
    "DEVA", "SELEC", "ECILC", "GENIL", "TRILC", "RTALB", "MPARK", "LKMNH", "KORDS",
    "BAGFS", "EGGUB", "DEVA", "DYOBY",

    # Food, Beverage & Agriculture
    "ULKER", "AEFES", "TATGD", "PNSUT", "PETUN", "KERVT", "DARDL", "BANVT", "YYLGD",
    "ULUUN", "GOKNR", "TUKAS", "FADE", "KRVGD", "KUTPO", "OYYAT", "AVOD",

    # Transportation & Logistics
    "CLEBI", "RYSAS", "REYSA", "GSDDE",

    # Sports Clubs
    "FENER", "GSRAY", "BJKAS", "TSPOR",
}

# ---------------------------------------------------------------------------
# Forex & Currency Pairs (appends =X for Yahoo Finance)
# ---------------------------------------------------------------------------
FOREX_PAIRS = {
    # Turkish Lira crosses
    "USDTRY", "EURTRY", "GBPTRY", "CHFTRY", "CADTRY", "AUDTRY", "JPYTRY", "RUBTRY",
    "AEDTRY", "SARTRY", "CNYTRY", "AZNTRY", "QARTRY", "KWDTRY", "NOKTRY", "SEKTRY",

    # Major FX pairs
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",

    # European & Asian crosses
    "EURGBP", "EURJPY", "EURCHF", "EURAUD", "EURCAD", "EURNZD",
    "GBPJPY", "GBPCHF", "GBPAUD", "GBPCAD", "GBPNZD",
    "AUDJPY", "CADJPY", "CHFJPY", "NZDJPY",
    "AUDCAD", "AUDNZD", "AUDCHF", "CADCHF", "NZDCAD", "NZDCHF",

    # Emerging & Other currencies
    "USDCNY", "USDHKD", "USDSGD", "USDINR", "USDKRW", "USDMXN", "USDBRL", "USDZAR",
    "USDPLN", "USDSEK", "USDNOK",
}

# ---------------------------------------------------------------------------
# Major Indices & Futures Mappings
# ---------------------------------------------------------------------------
INDEX_MAP = {
    # Borsa Istanbul Indices
    "XU100": "XU100.IS",
    "BIST100": "XU100.IS",
    "BIST": "XU100.IS",
    "BORSA": "XU100.IS",
    "XU030": "XU030.IS",
    "BIST30": "XU030.IS",
    "XBANK": "XBANK.IS",
    "BISTBANKA": "XBANK.IS",
    "XUSIN": "XUSIN.IS",
    "BISTSINAI": "XUSIN.IS",
    "XBLSM": "XBLSM.IS",
    "BISTBILISIM": "XBLSM.IS",
    "XGIDA": "XGIDA.IS",
    "XUTEK": "XUTEK.IS",
    "XGMYO": "XGMYO.IS",
    "XINSA": "XINSA.IS",
    "XELKT": "XELKT.IS",
    "XHOLD": "XHOLD.IS",
    "XILTM": "XILTM.IS",
    "XSPOR": "XSPOR.IS",
    "XKMYA": "XKMYA.IS",
    "XTRZM": "XTRZM.IS",

    # US Major Indices & Tech
    "NASDAQ": "^NDX",
    "NASDAQ100": "^NDX",
    "NDX": "^NDX",
    "NAS100": "^NDX",
    "US100": "^NDX",
    "USTECH100": "^NDX",
    "USTECH": "^NDX",
    "NQ": "NQ=F",
    "MNQ": "MNQ=F",
    "IXIC": "^IXIC",
    "COMPOSITE": "^IXIC",
    "NASDAQCOMPOSITE": "^IXIC",
    "QQQ": "QQQ",
    "TQQQ": "TQQQ",
    "SQQQ": "SQQQ",

    "SP500": "^GSPC",
    "S&P500": "^GSPC",
    "SPX": "^GSPC",
    "US500": "^GSPC",
    "INX": "^GSPC",
    "ES": "ES=F",
    "MES": "MES=F",
    "SPY": "SPY",
    "VOO": "VOO",
    "IVV": "IVV",

    "DOW": "^DJI",
    "DJI": "^DJI",
    "DOWJONES": "^DJI",
    "US30": "^DJI",
    "DJIA": "^DJI",
    "YM": "YM=F",
    "MYM": "MYM=F",
    "DIA": "DIA",

    "RUSSELL": "^RUT",
    "RUSSELL2000": "^RUT",
    "RUT": "^RUT",
    "US2000": "^RUT",
    "IWM": "IWM",

    # Volatility Index
    "VIX": "^VIX",
    "VOLATILITY": "^VIX",
    "KORKU": "^VIX",

    # European & Global Indices
    "DAX": "^GDAXI",
    "DAX40": "^GDAXI",
    "GER40": "^GDAXI",
    "GERMANY40": "^GDAXI",
    "FTSE": "^FTSE",
    "UK100": "^FTSE",
    "FTSE100": "^FTSE",
    "CAC": "^FCHI",
    "CAC40": "^FCHI",
    "FRA40": "^FCHI",
    "NIKKEI": "^N225",
    "NIKKEI225": "^N225",
    "N225": "^N225",
    "JPN225": "^N225",
    "HANGSENG": "^HSI",
    "HSI": "^HSI",
    "HK50": "^HSI",
    "EUROSTOXX": "^STOXX50E",
    "STOXX50": "^STOXX50E",
    "SX5E": "^STOXX50E",
    "EU50": "^STOXX50E",
    "SHANGHAI": "000001.SS",
    "SSEC": "000001.SS",
    "SSE": "000001.SS",
    "KOSPI": "^KS11",
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
    "SENSEX": "^BSESN",
    "TSX": "^GSPTSE",
    "ASX": "^AXJO",
    "ASX200": "^AXJO",
    "BOVESPA": "^BVSP",

    # Dollar Index & US Bond Yields
    "DXY": "DX-Y.NYB",
    "DX-Y": "DX-Y.NYB",
    "USDX": "DX-Y.NYB",
    "DOLLARINDEX": "DX-Y.NYB",
    "US10Y": "^TNX",
    "TNX": "^TNX",
    "10Y": "^TNX",
    "US30Y": "^TYX",
    "30Y": "^TYX",
    "US05Y": "^FVX",
    "5Y": "^FVX",
    "US02Y": "^IRX",
    "2Y": "^IRX",
}

# ---------------------------------------------------------------------------
# Commodities (Futures mappings on Yahoo Finance)
# ---------------------------------------------------------------------------
COMMODITY_MAP = {
    # Precious & Industrial Metals
    "GOLD": "GC=F",
    "ALTIN": "GC=F",
    "ONS": "GC=F",
    "ONSALTIN": "GC=F",
    "XAU": "GC=F",
    "XAUUSD": "GC=F",
    "SILVER": "SI=F",
    "GUMUS": "SI=F",
    "ONSGUMUS": "SI=F",
    "XAG": "SI=F",
    "XAGUSD": "SI=F",
    "PLATINUM": "PL=F",
    "PLATIN": "PL=F",
    "XPT": "PL=F",
    "PALLADIUM": "PA=F",
    "PALADYUM": "PA=F",
    "XPD": "PA=F",
    "COPPER": "HG=F",
    "BAKIR": "HG=F",
    "ALUMINUM": "ALI=F",
    "ALUMINYUM": "ALI=F",

    # Energy Commodities
    "BRENT": "BZ=F",
    "BRENTPETROL": "BZ=F",
    "UKOIL": "BZ=F",
    "CRUDE": "CL=F",
    "OIL": "CL=F",
    "PETROL": "CL=F",
    "WTI": "CL=F",
    "USOIL": "CL=F",
    "HAM_PETROL": "CL=F",
    "NATGAS": "NG=F",
    "DOGALGAZ": "NG=F",
    "GASOLINE": "RB=F",
    "BENZIN": "RB=F",
    "HEATINGOIL": "HO=F",

    # Agriculture & Softs
    "WHEAT": "ZW=F",
    "BUGDAY": "ZW=F",
    "CORN": "ZC=F",
    "MISIR": "ZC=F",
    "SOYBEAN": "ZS=F",
    "SOYA": "ZS=F",
    "COFFEE": "KC=F",
    "KAHVE": "KC=F",
    "SUGAR": "SB=F",
    "SEKER": "SB=F",
    "COTTON": "CT=F",
    "PAMUK": "CT=F",
    "COCOA": "CC=F",
    "KAKAO": "CC=F",
}

# ---------------------------------------------------------------------------
# Crypto Shorthand Aliases (mapped to *USDT on Binance)
# ---------------------------------------------------------------------------
CRYPTO_SHORTHAND = {
    # Top 20 Market Cap
    "BTC": "BTCUSDT",
    "BITCOIN": "BTCUSDT",
    "ETH": "ETHUSDT",
    "ETHEREUM": "ETHUSDT",
    "SOL": "SOLUSDT",
    "SOLANA": "SOLUSDT",
    "BNB": "BNBUSDT",
    "BINANCE": "BNBUSDT",
    "XRP": "XRPUSDT",
    "RIPPLE": "XRPUSDT",
    "DOGE": "DOGEUSDT",
    "DOGECOIN": "DOGEUSDT",
    "ADA": "ADAUSDT",
    "CARDANO": "ADAUSDT",
    "AVAX": "AVAXUSDT",
    "AVALANCHE": "AVAXUSDT",
    "SUI": "SUIUSDT",
    "DOT": "DOTUSDT",
    "POLKADOT": "DOTUSDT",
    "LINK": "LINKUSDT",
    "CHAINLINK": "LINKUSDT",
    "TRX": "TRXUSDT",
    "TRON": "TRXUSDT",
    "TON": "TONUSDT",
    "TONCOIN": "TONUSDT",
    "SHIB": "SHIBUSDT",
    "SHIBA": "SHIBAUSDT",
    "NEAR": "NEARUSDT",
    "APT": "APTUSDT",
    "APTOS": "APTUSDT",
    "POL": "POLUSDT",
    "MATIC": "POLUSDT",
    "POLYGON": "POLUSDT",
    "LTC": "LTCUSDT",
    "LITECOIN": "LTCUSDT",
    "BCH": "BCHUSDT",
    "BITCOINCASH": "BCHUSDT",
    "UNI": "UNIUSDT",
    "UNISWAP": "UNIUSDT",
    "XLM": "XLMUSDT",
    "STELLAR": "XLMUSDT",
    "ETC": "ETCUSDT",
    "ETHEREUMCLASSIC": "ETCUSDT",

    # AI & DePIN Tokens
    "FET": "FETUSDT",
    "ASI": "FETUSDT",
    "TAO": "TAOUSDT",
    "BITTENSOR": "TAOUSDT",
    "RENDER": "RENDERUSDT",
    "RNDR": "RENDERUSDT",
    "INJ": "INJUSDT",
    "INJECTIVE": "INJUSDT",
    "GRT": "GRTUSDT",
    "THEGRAPH": "GRTUSDT",
    "AR": "ARUSDT",
    "ARWEAVE": "ARUSDT",
    "FIL": "FILUSDT",
    "FILECOIN": "FILUSDT",
    "ICP": "ICPUSDT",
    "INTERNETCOMPUTER": "ICPUSDT",
    "IO": "IOUSDT",
    "ATH": "ATHUSDT",
    "AETHIR": "ATHUSDT",

    # Layer 1 & Layer 2 Chains
    "TIA": "TIAUSDT",
    "CELESTIA": "TIAUSDT",
    "SEI": "SEIUSDT",
    "ARB": "ARBUSDT",
    "ARBITRUM": "ARBUSDT",
    "OP": "OPUSDT",
    "OPTIMISM": "OPUSDT",
    "STRK": "STRKUSDT",
    "STARKNET": "STRKUSDT",
    "HBAR": "HBARUSDT",
    "HEDERA": "HBARUSDT",
    "ATOM": "ATOMUSDT",
    "COSMOS": "ATOMUSDT",
    "STX": "STXUSDT",
    "STACKS": "STXUSDT",
    "IMX": "IMXUSDT",
    "IMMUTABLE": "IMXUSDT",
    "FTM": "FTMUSDT",
    "FANTOM": "FTMUSDT",
    "SONIC": "FTMUSDT",
    "ALGO": "ALGOUSDT",
    "ALGORAND": "ALGOUSDT",
    "VET": "VETUSDT",
    "VECHAIN": "VETUSDT",
    "KAS": "KASUSDT",
    "KASPA": "KASUSDT",
    "EGLD": "EGLDUSDT",
    "MULTIVERSX": "EGLDUSDT",
    "CFX": "CFXUSDT",
    "CONFLUX": "CFXUSDT",
    "CKB": "CKBUSDT",
    "NERVOS": "CKBUSDT",
    "RON": "RONINUSDT",
    "RONIN": "RONINUSDT",
    "BEAM": "BEAMUSDT",
    "ZK": "ZKUSDT",
    "ZKSYNC": "ZKUSDT",

    # DeFi & Yield
    "AAVE": "AAVEUSDT",
    "MKR": "MKRUSDT",
    "MAKER": "MKRUSDT",
    "RUNE": "RUNEUSDT",
    "THORCHAIN": "RUNEUSDT",
    "ONDO": "ONDOUSDT",
    "PENDLE": "PENDLEUSDT",
    "JUP": "JUPUSDT",
    "JUPITER": "JUPUSDT",
    "PYTH": "PYTHUSDT",
    "ENA": "ENAUSDT",
    "ETHENA": "ENAUSDT",
    "CRV": "CRVUSDT",
    "CURVE": "CRVUSDT",
    "LDO": "LDOUSDT",
    "LIDO": "LDOUSDT",
    "DYDX": "DYDXUSDT",
    "SNX": "SNXUSDT",
    "1INCH": "1INCHUSDT",
    "GMX": "GMXUSDT",
    "CAKE": "CAKEUSDT",
    "SUSHI": "SUSHIUSDT",
    "COMP": "COMPUSDT",

    # Meme Coins & Community Tokens
    "PEPE": "PEPEUSDT",
    "WIF": "WIFUSDT",
    "DOGWIFHAT": "WIFUSDT",
    "BONK": "BONKUSDT",
    "FLOKI": "FLOKIUSDT",
    "POPCAT": "POPCATUSDT",
    "BOME": "BOMEUSDT",
    "MEW": "MEWUSDT",
    "NEIRO": "NEIROUSDT",
    "TURBO": "TURBOUSDT",
    "BABYDOGE": "1MBABYDOGEUSDT",
    "MEME": "MEMEUSDT",

    # Telegram / TON Ecosystem & Gaming
    "NOT": "NOTUSDT",
    "NOTCOIN": "NOTUSDT",
    "DOGS": "DOGSUSDT",
    "HMSTR": "HMSTRUSDT",
    "HAMSTER": "HMSTRUSDT",
    "CATI": "CATIUSDT",
    "GALA": "GALAUSDT",
    "AXS": "AXSUSDT",
    "SAND": "SANDUSDT",
    "MANA": "MANAUSDT",
    "CHZ": "CHZUSDT",
    "CHILIZ": "CHZUSDT",

    # Other Notable Coins
    "WLD": "WLDUSDT",
    "WORLDCOIN": "WLDUSDT",
    "JASMY": "JASMYUSDT",
    "ORDI": "ORDIUSDT",
    "SATS": "1000SATSUSDT",
    "OM": "OMUSDT",
    "MANTRA": "OMUSDT",
    "ROSE": "ROSEUSDT",
    "KAVA": "KAVAUSDT",
    "ZIL": "ZILUSDT",
    "ENJ": "ENJUSDT",
    "BLUR": "BLURUSDT",
    "TRB": "TRBUSDT",
    "QNT": "QNTUSDT",
    "XMR": "XMRUSDT",
    "MONERO": "XMRUSDT",
    "ZEC": "ZECUSDT",
    "DASH": "DASHUSDT",
    "EOS": "EOSUSDT",
    "NEO": "NEOUSDT",
    "IOTA": "IOTAUSDT",
    "XTZ": "XTZUSDT",
}


def classify_and_normalize(raw_symbol: str) -> Tuple[str, str]:
    """Normalize input symbol and determine whether it routes to Binance WS or Yahoo Finance.

    :param raw_symbol: User inputted symbol (e.g., btcusdt, btc, NASDAQ, XU100, xau, THYAO, USDTRY)
    :return: (normalized_symbol, asset_type) where asset_type is 'CRYPTO' or 'EQUITY_FOREX'
    """
    clean = raw_symbol.strip().upper()

    # Strip prefixes like BINANCE: or BIST: or TV:
    if ":" in clean:
        _, clean = clean.split(":", 1)

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


# ---------------------------------------------------------------------------
# Rich Autocomplete Suggestions Catalog (Label, Value)
# Max choices returned to Discord is 25, filtered by user search.
# ---------------------------------------------------------------------------
AUTOCOMPLETE_PRESETS = [
    # Top Cryptocurrencies
    ("BTCUSDT (Bitcoin / BTC)", "BTCUSDT"),
    ("ETHUSDT (Ethereum / ETH)", "ETHUSDT"),
    ("SOLUSDT (Solana / SOL)", "SOLUSDT"),
    ("PEPEUSDT (Pepe Coin)", "PEPEUSDT"),
    ("DOGEUSDT (Dogecoin / DOGE)", "DOGEUSDT"),
    ("XRPUSDT (Ripple / XRP)", "XRPUSDT"),
    ("AVAXUSDT (Avalanche / AVAX)", "AVAXUSDT"),
    ("SUIUSDT (Sui Network)", "SUIUSDT"),
    ("BNBUSDT (Binance Coin / BNB)", "BNBUSDT"),
    ("LINKUSDT (Chainlink / LINK)", "LINKUSDT"),
    ("NEARUSDT (Near Protocol)", "NEARUSDT"),
    ("TONUSDT (Toncoin / Telegram)", "TONUSDT"),
    ("SHIBUSDT (Shiba Inu / SHIB)", "SHIBUSDT"),
    ("WIFUSDT (dogwifhat / WIF)", "WIFUSDT"),
    ("APTUSDT (Aptos / APT)", "APTUSDT"),
    ("FETUSDT (Artificial Superintelligence)", "FETUSDT"),
    ("TAOUSDT (Bittensor / TAO)", "TAOUSDT"),
    ("RENDERUSDT (Render / RNDR)", "RENDERUSDT"),
    ("ARBUSDT (Arbitrum / ARB)", "ARBUSDT"),
    ("OPUSDT (Optimism / OP)", "OPUSDT"),
    ("TIAUSDT (Celestia / TIA)", "TIAUSDT"),
    ("INJUSDT (Injective / INJ)", "INJUSDT"),
    ("ONDOUSDT (Ondo Finance)", "ONDOUSDT"),
    ("PENDLEUSDT (Pendle Yield)", "PENDLEUSDT"),
    ("WLDUSDT (Worldcoin / WLD)", "WLDUSDT"),
    ("BONKUSDT (Bonk / BONK)", "BONKUSDT"),
    ("FLOKIUSDT (Floki Inu)", "FLOKIUSDT"),
    ("POPCATUSDT (Popcat)", "POPCATUSDT"),
    ("DOTUSDT (Polkadot / DOT)", "DOTUSDT"),
    ("LTCUSDT (Litecoin / LTC)", "LTCUSDT"),
    ("AAVEUSDT (Aave DeFi)", "AAVEUSDT"),
    ("UNIUSDT (Uniswap / UNI)", "UNIUSDT"),
    ("NOTUSDT (Notcoin / NOT)", "NOTUSDT"),
    ("KASUSDT (Kaspa / KAS)", "KASUSDT"),

    # Commodities & Precious Metals
    ("GOLD / XAU (Ons Altın / GC=F)", "GOLD"),
    ("SILVER / XAG (Gümüş / SI=F)", "SILVER"),
    ("BRENT (Brent Ham Petrol / BZ=F)", "BRENT"),
    ("CRUDE / WTI (ABD Ham Petrol / CL=F)", "OIL"),
    ("NATGAS (Doğal Gaz / NG=F)", "NATGAS"),
    ("COPPER (Bakır / HG=F)", "COPPER"),
    ("PLATINUM (Platin / PL=F)", "PLATINUM"),
    ("COFFEE (Kahve / KC=F)", "COFFEE"),
    ("WHEAT (Buğday / ZW=F)", "WHEAT"),
    ("CORN (Mısır / ZC=F)", "CORN"),
    ("SUGAR (Şeker / SB=F)", "SUGAR"),
    ("COCOA (Kakao / CC=F)", "COCOA"),

    # Major Global & Local Indices
    ("XU100 (BIST 100 Endeksi)", "XU100"),
    ("XU030 (BIST 30 Endeksi)", "XU030"),
    ("XBANK (BIST Bankacılık Endeksi)", "XBANK"),
    ("XUSIN (BIST Sınai Endeksi)", "XUSIN"),
    ("NASDAQ (Nasdaq 100 / US100 / ^NDX)", "NASDAQ"),
    ("NQ (E-mini Nasdaq 100 Vadeli / NQ=F)", "NQ"),
    ("DJI (Dow Jones 30 / US30 / ^DJI)", "DJI"),
    ("YM (E-mini Dow Jones Vadeli / YM=F)", "YM"),
    ("SP500 (S&P 500 Endeksi / ^GSPC)", "SP500"),
    ("ES (E-mini S&P 500 Vadeli / ES=F)", "ES"),
    ("DAX (Almanya DAX 40 / GER40 / ^GDAXI)", "DAX"),
    ("FTSE (İngiltere FTSE 100 / UK100 / ^FTSE)", "FTSE"),
    ("CAC40 (Fransa CAC 40 / ^FCHI)", "CAC"),
    ("NIKKEI (Japonya Nikkei 225 / ^N225)", "NIKKEI"),
    ("HANGSENG (Hong Kong Hang Seng / ^HSI)", "HANGSENG"),
    ("DXY (Dolar Endeksi / DX-Y.NYB)", "DXY"),
    ("VIX (Korku / Volatilite Endeksi / ^VIX)", "VIX"),
    ("US10Y (ABD 10 Yıllık Tahvil Faizi / ^TNX)", "US10Y"),

    # Borsa Istanbul (BIST) Popular Equities
    ("THYAO (Türk Hava Yolları)", "THYAO"),
    ("ASELS (Aselsan Savunma)", "ASELS"),
    ("GARAN (Garanti BBVA)", "GARAN"),
    ("EREGL (Ereğli Demir Çelik)", "EREGL"),
    ("SISE (Türkiye Şişecam)", "SISE"),
    ("KCHOL (Koç Holding)", "KCHOL"),
    ("TUPRS (Tüpraş Rafineri)", "TUPRS"),
    ("AKBNK (Akbank)", "AKBNK"),
    ("YKBNK (Yapı ve Kredi Bankası)", "YKBNK"),
    ("SAHOL (Sabancı Holding)", "SAHOL"),
    ("FROTO (Ford Otosan)", "FROTO"),
    ("TOASO (Tofaş Otomobil)", "TOASO"),
    ("BIMAS (BİM Birleşik Mağazalar)", "BIMAS"),
    ("MGROS (Migros Ticaret)", "MGROS"),
    ("PETKM (Petkim Petrokimya)", "PETKM"),
    ("PGSUS (Pegasus Hava Taşımacılığı)", "PGSUS"),
    ("TCELL (Turkcell İletişim)", "TCELL"),
    ("TTKOM (Türk Telekom)", "TTKOM"),
    ("KOZAL (Koza Altın)", "KOZAL"),
    ("EKGYO (Emlak Konut GYO)", "EKGYO"),
    ("ASTOR (Astor Enerji)", "ASTOR"),
    ("KONTR (Kontrolmatik Teknoloji)", "KONTR"),
    ("ALARK (Alarko Holding)", "ALARK"),
    ("ODAS (Odaş Elektrik)", "ODAS"),
    ("CANTE (Çan2 Termik)", "CANTE"),
    ("EUPWR (Europower Enerji)", "EUPWR"),
    ("CWENE (CW Enerji)", "CWENE"),
    ("REEDR (Reeder Teknoloji)", "REEDR"),
    ("MIATK (Mia Teknoloji)", "MIATK"),
    ("BRSAN (Borusan Boru)", "BRSAN"),
    ("TABGD (TAB Gıda)", "TABGD"),
    ("TAVHL (TAV Havalimanları)", "TAVHL"),
    ("CCOLA (Coca-Cola İçecek)", "CCOLA"),
    ("MAVI (Mavi Giyim)", "MAVI"),
    ("OTKAR (Otokar)", "OTKAR"),
    ("ENJSA (Enerjisa Enerji)", "ENJSA"),
    ("AKSEN (Aksa Enerji)", "AKSEN"),
    ("ZOREN (Zorlu Enerji)", "ZOREN"),
    ("SASA (Sasa Polyester)", "SASA"),
    ("HEKTS (Hektaş)", "HEKTS"),
    ("GUBRF (Gübre Fabrikaları)", "GUBRF"),
    ("ULKER (Ülker Bisküvi)", "ULKER"),
    ("AEFES (Anadolu Efes)", "AEFES"),
    ("ISCTR (İş Bankası C)", "ISCTR"),
    ("VAKBN (Vakıflar Bankası)", "VAKBN"),
    ("HALKB (Halkbank)", "HALKB"),
    ("KRDMD (Kardemir D)", "KRDMD"),
    ("OYAKC (Oyak Çimento)", "OYAKC"),
    ("CIMSA (Çimsa Çimento)", "CIMSA"),
    ("SOKM (Şok Marketler)", "SOKM"),
    ("DOAS (Doğuş Otomotiv)", "DOAS"),
    ("CLEBI (Çelebi Hava Servisi)", "CLEBI"),
    ("SDTTR (SDT Uzay ve Savunma)", "SDTTR"),
    ("PAPIL (Papilon Savunma)", "PAPIL"),
    ("ARDYZ (Ardıç Teknoloji)", "ARDYZ"),
    ("PATEK (Pasifik Teknoloji)", "PATEK"),
    ("BINHO (1000 Yatırımlar)", "BINHO"),
    ("ALVES (Alves Kablo)", "ALVES"),
    ("AGROT (Agrotech)", "AGROT"),
    ("GESAN (Girişim Elektrik)", "GESAN"),
    ("ALFAS (Alfa Solar Enerji)", "ALFAS"),
    ("SMRTG (Smart Güneş Enerjisi)", "SMRTG"),
    ("YEOTK (Yeo Teknoloji)", "YEOTK"),
    ("MOGAN (Mogan Enerji)", "MOGAN"),
    ("KOPOL (Koza Polyester)", "KOPOL"),
    ("CVKMD (CVK Maden)", "CVKMD"),
    ("FENER (Fenerbahçe Futbol)", "FENER"),
    ("GSRAY (Galatasaray Sportif)", "GSRAY"),
    ("BJKAS (Beşiktaş Futbol)", "BJKAS"),
    ("TSPOR (Trabzonspor Sportif)", "TSPOR"),

    # US & Global Equities (Tech Giants & Blue Chips)
    ("NVDA (NVIDIA Corporation)", "NVDA"),
    ("AAPL (Apple Inc.)", "AAPL"),
    ("TSLA (Tesla Inc.)", "TSLA"),
    ("MSFT (Microsoft Corporation)", "MSFT"),
    ("AMZN (Amazon.com Inc.)", "AMZN"),
    ("GOOGL (Alphabet / Google Class A)", "GOOGL"),
    ("META (Meta Platforms / Facebook)", "META"),
    ("NFLX (Netflix Inc.)", "NFLX"),
    ("AMD (Advanced Micro Devices)", "AMD"),
    ("INTC (Intel Corporation)", "INTC"),
    ("PLTR (Palantir Technologies)", "PLTR"),
    ("COIN (Coinbase Global)", "COIN"),
    ("MSTR (MicroStrategy)", "MSTR"),
    ("SMCI (Super Micro Computer)", "SMCI"),
    ("AVGO (Broadcom Inc.)", "AVGO"),
    ("QCOM (Qualcomm Inc.)", "QCOM"),
    ("ARM (Arm Holdings)", "ARM"),
    ("TSM (Taiwan Semiconductor / TSMC)", "TSM"),
    ("BABA (Alibaba Group)", "BABA"),
    ("UBER (Uber Technologies)", "UBER"),
    ("DIS (Walt Disney Company)", "DIS"),
    ("BA (Boeing Company)", "BA"),
    ("JPM (JPMorgan Chase & Co.)", "JPM"),
    ("V (Visa Inc.)", "V"),
    ("MA (Mastercard Inc.)", "MA"),
    ("NKE (Nike Inc.)", "NKE"),
    ("SBUX (Starbucks Corp.)", "SBUX"),
    ("MCD (McDonald's Corp.)", "MCD"),
    ("WMT (Walmart Inc.)", "WMT"),
    ("COST (Costco Wholesale)", "COST"),
    ("KO (Coca-Cola US)", "KO"),
    ("PEP (PepsiCo Inc.)", "PEP"),
    ("XOM (Exxon Mobil Corp.)", "XOM"),
    ("CVX (Chevron Corporation)", "CVX"),
    ("LLY (Eli Lilly and Company)", "LLY"),
    ("SPY (SPDR S&P 500 ETF Trust)", "SPY"),
    ("QQQ (Invesco QQQ Trust ETF)", "QQQ"),

    # Forex & Fiat Currency Pairs
    ("USDTRY (Dolar / Türk Lirası)", "USDTRY"),
    ("EURTRY (Euro / Türk Lirası)", "EURTRY"),
    ("GBPTRY (İngiliz Sterlini / TL)", "GBPTRY"),
    ("CHFTRY (İsviçre Frangı / TL)", "CHFTRY"),
    ("EURUSD (Euro / Amerikan Doları)", "EURUSD"),
    ("GBPUSD (İngiliz Sterlini / ABD Doları)", "GBPUSD"),
    ("USDJPY (ABD Doları / Japon Yeni)", "USDJPY"),
    ("USDCHF (ABD Doları / İsviçre Frangı)", "USDCHF"),
    ("AUDUSD (Avustralya Doları / ABD Doları)", "AUDUSD"),
    ("USDCAD (ABD Doları / Kanada Doları)", "USDCAD"),
]


def get_symbol_autocomplete(current: str) -> list[tuple[str, str]]:
    """Return filtered autocomplete choices matching user input (max 25 choices for Discord)."""
    clean = current.strip().upper()
    if not clean:
        return AUTOCOMPLETE_PRESETS[:25]

    matches = []
    for label, val in AUTOCOMPLETE_PRESETS:
        if clean in val.upper() or clean in label.upper():
            matches.append((label, val))

    # If user typed a custom ticker not in presets, keep custom at the top
    if not any(val.upper() == clean for _, val in matches):
        matches.insert(0, (f"Özel Sembol: {clean}", clean))

    return matches[:25]

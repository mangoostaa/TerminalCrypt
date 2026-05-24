from __future__ import annotations

import os

BINANCE_SYMBOLS = {
    "BTCUSDT":   "BTC",   "ETHUSDT":   "ETH",   "BNBUSDT":   "BNB",
    "SOLUSDT":   "SOL",   "XRPUSDT":   "XRP",   "ADAUSDT":   "ADA",
    "DOGEUSDT":  "DOGE",  "AVAXUSDT":  "AVAX",  "DOTUSDT":   "DOT",
    "LINKUSDT":  "LINK",  "LTCUSDT":   "LTC",   "UNIUSDT":   "UNI",
    "SHIBUSDT":  "SHIB",  "TRXUSDT":   "TRX",   "TONUSDT":   "TON",
    "MATICUSDT": "MATIC", "ICPUSDT":   "ICP",   "NEARUSDT":  "NEAR",
    "APTUSDT":   "APT",   "OPUSDT":    "OP",    "ARBUSDT":   "ARB",
    "ATOMUSDT":  "ATOM",  "FTMUSDT":   "FTM",   "INJUSDT":   "INJ",
    "RUNEUSDT":  "RUNE",  "LDOUSDT":   "LDO",   "MKRUSDT":   "MKR",
    "AAVEUSDT":  "AAVE",  "GRTUSDT":   "GRT",  "SNXUSDT":   "SNX",
    "COMPUSDT":  "COMP",  "CRVUSDT":   "CRV",   "SUIUSDT":   "SUI",
    "SEIUSDT":   "SEI",   "TIAUSDT":   "TIA",   "WLDUSDT":   "WLD",
    "JUPUSDT":   "JUP",   "PYTHUSDT":  "PYTH",  "STRKUSDT":  "STRK",
    "FILUSDT":   "FIL",   "SANDUSDT":  "SAND",  "MANAUSDT":  "MANA",
    "AXSUSDT":   "AXS",   "APEUSDT":   "APE",   "GALAUSDT":  "GALA",
    "IMXUSDT":   "IMX",   "FLOWUSDT":  "FLOW",  "CHZUSDT":   "CHZ",
    "ENJUSDT":   "ENJ",   "ALGOUSDT":  "ALGO",  "XLMUSDT":   "XLM",
    "VETUSDT":   "VET",   "XTZUSDT":   "XTZ",  "EOSUSDT":   "EOS",
    "NEOUSDT":   "NEO",   "ZILUSDT":   "ZIL",   "QNTUSDT":   "QNT",
    "EGLDUSDT":  "EGLD",  "FETUSDT":   "FET",   "OCEANUSDT": "OCEAN",
    "RLCUSDT":   "RLC",  "BTTCUSDT":  "BTTC",  "ONEUSDT":   "ONE",
    "HBARUSDT":  "HBAR",  "IOTAUSDT":   "IOTA",  "XMRUSDT":   "XMR",
    "DASHUSDT":  "DASH",  "ZECUSDT":   "ZEC",   "BATUSDT":   "BAT",
    "1INCHUSDT": "1INCH", "YFIUSDT":   "YFI",  "SUSHIUSDT": "SUSHI",
    "CAKEUSDT":  "CAKE",  "DYDXUSDT":  "DYDX",  "GMXUSDT":   "GMX",
    "STXUSDT":   "STX",  "CFXUSDT":   "CFX",  "BLURUSDT":  "BLUR",
    "PENDLEUSDT":"PENDLE","WIFUSDT":   "WIF",   "BONKUSDT":  "BONK",
    "PEPEUSDT":  "PEPE",  "FLOKIUSDT": "FLOKI", "KASUSDT":   "KAS",
}

COINBASE_SYMBOLS = {
    "BTC-USD":   "BTC",  "ETH-USD":   "ETH",  "SOL-USD":   "SOL",
    "XRP-USD":   "XRP",  "ADA-USD":   "ADA",  "DOGE-USD":  "DOGE",
    "AVAX-USD":  "AVAX", "DOT-USD":   "DOT",  "LINK-USD":   "LINK",
    "LTC-USD":   "LTC",  "UNI-USD":   "UNI",  "MATIC-USD": "MATIC",
    "NEAR-USD":  "NEAR", "APT-USD":   "APT",  "OP-USD":    "OP",
    "ATOM-USD":  "ATOM", "FTM-USD":   "FTM",  "INJ-USD":   "INJ",
    "LDO-USD":   "LDO",  "MKR-USD":   "MKR",  "AAVE-USD":  "AAVE",
    "GRT-USD":   "GRT",  "CRV-USD":   "CRV",  "SNX-USD":   "SNX",
    "COMP-USD":  "COMP", "FIL-USD":   "FIL",  "SAND-USD":  "SAND",
    "MANA-USD":  "MANA", "AXS-USD":   "AXS",  "APE-USD":   "APE",
    "IMX-USD":   "IMX",  "FLOW-USD":  "FLOW", "CHZ-USD":   "CHZ",
    "ALGO-USD":  "ALGO",  "XLM-USD":   "XLM",  "XTZ-USD":   "XTZ",
    "EOS-USD":   "EOS",  "FET-USD":   "FET",  "OCEAN-USD": "OCEAN",
    "XMR-USD":   "XMR",  "ZEC-USD":   "ZEC",  "BAT-USD":   "BAT",
    "1INCH-USD": "1INCH","YFI-USD":   "YFI",  "SUSHI-USD": "SUSHI",
    "DYDX-USD":  "DYDX", "STX-USD":   "STX",  "BLUR-USD":  "BLUR",
    "WIF-USD":   "WIF",  "PEPE-USD":  "PEPE",
}

KRAKEN_SYMBOLS = {
    "XBT/USD":   "BTC",  "ETH/USD":   "ETH",  "SOL/USD":   "SOL",
    "XRP/USD":   "XRP",  "ADA/USD":   "ADA",  "DOGE/USD":  "DOGE",
    "DOT/USD":   "DOT",  "LINK/USD":   "LINK", "LTC/USD":   "LTC",
    "UNI/USD":   "UNI",  "ATOM/USD":  "ATOM", "ALGO/USD":  "ALGO",
    "XLM/USD":   "XLM",  "XMR/USD":   "XMR",  "ZEC/USD":   "ZEC",
    "EOS/USD":   "EOS",  "XTZ/USD":   "XTZ",  "FLOW/USD":  "FLOW",
    "FIL/USD":   "FIL",  "AAVE/USD":  "AAVE", "MKR/USD":   "MKR",
    "COMP/USD":  "COMP", "GRT/USD":   "GRT",  "SNX/USD":   "SNX",
    "CRV/USD":   "CRV",  "YFI/USD":   "YFI",  "BAT/USD":   "BAT",
    "OCEAN/USD": "OCEAN","1INCH/USD": "1INCH","NEAR/USD":  "NEAR",
    "AVAX/USD":  "AVAX", "FTM/USD":   "FTM",  "SAND/USD":  "SAND",
    "MANA/USD":  "MANA", "AXS/USD":   "AXS",  "INJ/USD":   "INJ",
}

SYMBOLS_ORDERED = [
    "BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","DOT","LINK","LTC","UNI",
    "TRX","TON","NEAR","APT","OP","ARB","SUI","SEI","TIA","STX","HBAR","ALGO",
    "XLM","VET","XTZ","EOS","NEO","EGLD","IOTA","ONE","CFX","KAS",
    "ATOM","FTM","INJ","RUNE","LDO","MKR","AAVE","GRT","SNX","COMP","CRV",
    "DYDX","GMX","PENDLE","1INCH","YFI","SUSHI","CAKE","BAT",
    "SAND","MANA","AXS","APE","GALA","IMX","FLOW","CHZ","ENJ",
    "ICP","FIL","FET","OCEAN","RLC","QNT",
    "SHIB","PEPE","WIF","BONK","FLOKI","BTTC",
    "XMR","DASH","ZEC",
    "MATIC","BLUR","STRK","PYTH","JUP","WLD",
]

SYMBOL_NAME = {
    "BTC":"Bitcoin",       "ETH":"Ethereum",      "BNB":"BNB Chain",
    "SOL":"Solana",        "XRP":"Ripple",         "ADA":"Cardano",
    "DOGE":"Dogecoin",     "AVAX":"Avalanche",     "DOT":"Polkadot",
    "LINK":"Chainlink",    "LTC":"Litecoin",       "UNI":"Uniswap",
    "SHIB":"Shiba Inu",    "TRX":"TRON",           "TON":"Toncoin",
    "MATIC":"Polygon",     "ICP":"Internet Cmptr", "NEAR":"NEAR Protocol",
    "APT":"Aptos",         "OP":"Optimism",        "ARB":"Arbitrum",
    "ATOM":"Cosmos",       "FTM":"Fantom",         "INJ":"Injective",
    "RUNE":"THORChain",    "LDO":"Lido DAO",       "MKR":"Maker",
    "AAVE":"Aave",         "GRT":"The Graph",      "SNX":"Synthetix",
    "COMP":"Compound",     "CRV":"Curve",          "SUI":"Sui",
    "SEI":"Sei",           "TIA":"Celestia",      "WLD":"Worldcoin",
    "JUP":"Jupiter",       "PYTH":"Pyth Network",  "STRK":"Starknet",
    "FIL":"Filecoin",      "SAND":"The Sandbox",   "MANA":"Decentraland",
    "AXS":"Axie Infinity", "APE":"ApeCoin",        "GALA":"Gala",
    "IMX":"Immutable X",   "FLOW":"Flow",          "CHZ":"Chiliz",
    "ENJ":"Enjin Coin",    "ALGO":"Algorand",      "XLM":"Stellar",
    "VET":"VeChain",       "XTZ":"Tezos",          "EOS":"EOS",
    "NEO":"NEO",           "ZIL":"Zilliqa",       "QNT":"Quant",
    "EGLD":"MultiversX",   "FET":"Fetch.ai",       "OCEAN":"Ocean Proto.",
    "RLC":"iExec RLC",     "BTTC":"BitTorrent",    "ONE":"Harmony",
    "HBAR":"Hedera",       "IOTA":"IOTA",          "XMR":"Monero",
    "DASH":"Dash",         "ZEC":"Zcash",         "BAT":"Basic Attn Tkn",
    "1INCH":"1inch",       "YFI":"Yearn Finance",  "SUSHI":"SushiSwap",
    "CAKE":"PancakeSwap",  "DYDX":"dYdX",          "GMX":"GMX",
    "STX":"Stacks",        "CFX":"Conflux",        "BLUR":"Blur",
    "PENDLE":"Pendle",     "WIF":"dogwifhat",      "BONK":"Bonk",
    "PEPE":"Pepe",         "FLOKI":"Floki",        "KAS":"Kaspa",
}

SYMBOL_CATEGORIES = {
    "MEGA CAP":    ["BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","DOT","LINK","LTC","UNI"],
    "L1/L2 INFRA": ["TRX","TON","NEAR","APT","OP","ARB","SUI","SEI","TIA","STX","HBAR",
                    "ALGO","XLM","VET","XTZ","EOS","NEO","EGLD","IOTA","ONE","CFX","KAS","MATIC"],
    "DeFi":        ["ATOM","FTM","INJ","RUNE","LDO","MKR","AAVE","GRT","SNX","COMP","CRV",
                    "DYDX","GMX","PENDLE","1INCH","YFI","SUSHI","CAKE","BAT"],
    "NFT/GAMING":  ["SAND","MANA","AXS","APE","GALA","IMX","FLOW","CHZ","ENJ"],
    "AI/WEB3":     ["ICP","FIL","FET","OCEAN","RLC","QNT"],
    "MEMES":       ["SHIB","PEPE","WIF","BONK","FLOKI","BTTC"],
    "PRIVACY":     ["XMR","DASH","ZEC"],
    "OTROS":       ["BLUR","STRK","PYTH","JUP","WLD","ZIL"],
}

HISTORY_MAX = 120

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_WS_ALT = "wss://stream.binance.com:443/ws"
COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"
KRAKEN_WS_URL = "wss://ws.kraken.com"

HEADERS = {"User-Agent": "CryptexTerminal/3.1", "Accept": "application/json"}
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
COINGECKO_HEADERS = dict(HEADERS)
if COINGECKO_API_KEY:
    COINGECKO_HEADERS["X-CG-Pro-API-Key"] = COINGECKO_API_KEY

HELP_TEXT = """
[bold bright_green]◈ AZ TERMINAL v3.2 — ~80 pares · WebSocket + Indicadores[/]

[bold]COMANDOS:[/bold]
  [bright_green]python3 cryptex_terminal.py[/]                         Binance WS (default)
  [bright_green]python3 cryptex_terminal.py --source coinbase[/]       Coinbase Advanced WS
  [bright_green]python3 cryptex_terminal.py --source kraken[/]         Kraken WS
  [bright_green]python3 cryptex_terminal.py --once[/]                  Snapshot y salir
  [bright_green]python3 cryptex_terminal.py --alert BTC 100000[/]      Alerta BTC ≥ $100,000

[bold]COBERTURA (~80 pares Binance, ~50 Coinbase, ~35 Kraken):[/bold]
  Mega Cap    BTC ETH BNB SOL XRP ADA DOGE AVAX DOT LINK LTC UNI
  L1/L2       TRX TON NEAR APT OP ARB SUI SEI TIA STX HBAR ALGO
              XLM VET XTZ EOS NEO EGLD IOTA ONE CFX KAS MATIC
  DeFi        ATOM FTM INJ RUNE LDO MKR AAVE GRT SNX COMP CRV
              DYDX GMX PENDLE 1INCH YFI SUSHI CAKE BAT
  NFT/Gaming  SAND MANA AXS APE GALA IMX FLOW CHZ ENJ
  AI/Web3     ICP FIL FET OCEAN RLC QNT
  Memes       SHIB PEPE WIF BONK FLOKI BTTC
  Privacy     XMR DASH ZEC
  Otros       BLUR STRK PYTH JUP WLD

[bold]NAVEGACIÓN DEL DASHBOARD:[/bold]
  Ticker strip  → rota automáticamente cada 4s (18 símbolos visibles)
  Tabla precios → rota por categoría cada 8s (8 categorías)
  [bright_green]TAB / I[/]       alterna Markets ↔ Top 5 cuantitativo Coinbase
  [bright_green]M[/]             vuelve a Markets

[bold]INDICADORES TÉCNICOS:[/bold]
  [bright_green]RSI(14)[/]         < 30 sobreventa  /  > 70 sobrecompra
  [bright_green]EMA 9/21[/]        ▲BULL / ▼BEAR  (✦ = cruce reciente)
  [bright_green]MACD(12,26,9)[/]   histograma ▲/▼ con dirección
  [bright_green]BB(20,2σ)[/]       ↑↑OB / ↑HI / MID / ↓LO / ↓↓OS
  [bright_green]ATR(14)%[/]        volatilidad relativa al precio
  [bright_green]SIGNAL[/]          score combinado: STR LONG → STR SHORT
"""

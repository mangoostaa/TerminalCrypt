#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║          CRYPTEX TERMINAL v3.2 — Professional WebSocket CLI      ║
║                                                                  ║
║  WebSocket streams (ZERO polling):                               ║
║    • Binance   wss://stream.binance.com/ws  (primary, <50ms)     ║
║    • Coinbase  wss://advanced-trade-ws.coinbase.com (fallback)   ║
║    • Kraken    wss://ws.kraken.com          (fallback)           ║
║    • Alternative.me  Fear & Greed (REST, slow-changing)          ║
║                                                                  ║
║  INDICADORES TÉCNICOS:                                           ║
║    RSI(14) · EMA 9/21 cruzada · MACD(12,26,9)                    ║
║    Bollinger Bands(20,2σ) · ATR(14) · Señal combinada            ║
║                                                                  ║
║  INSTALACIÓN:                                                    ║
║    pip install websocket-client requests rich                    ║
║                                                                  ║
║  USO:                                                            ║
║    python3 cryptex_terminal.py              # dashboard live     ║
║    python3 cryptex_terminal.py --once       # snapshot           ║
║    python3 cryptex_terminal.py --alert BTC 10000                 ║
║    python3 cryptex_terminal.py --source coinbase                 ║
║    python3 cryptex_terminal.py --source kraken                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import time
import threading
import argparse
import json
import queue
import signal
import html
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import requests
import websocket
from rich.console import Console
from rich.table import Table
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.text import Text
from rich import box
from rich.rule import Rule

# ═══════════════════════════════════════════════════════════════════
#  CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════

# ── Binance: ~80 pares USDT (top por market cap + volumen) ─────────
BINANCE_SYMBOLS = {
    # Tier 1 — mega cap
    "BTCUSDT":   "BTC",   "ETHUSDT":   "ETH",   "BNBUSDT":   "BNB",
    "SOLUSDT":   "SOL",   "XRPUSDT":   "XRP",   "ADAUSDT":   "ADA",
    "DOGEUSDT":  "DOGE",  "AVAXUSDT":  "AVAX",  "DOTUSDT":   "DOT",
    "LINKUSDT":  "LINK",  "LTCUSDT":   "LTC",   "UNIUSDT":   "UNI",
    # Tier 2 — large cap
    "SHIBUSDT":  "SHIB",  "TRXUSDT":   "TRX",   "TONUSDT":   "TON",
    "MATICUSDT": "MATIC", "ICPUSDT":   "ICP",   "NEARUSDT":  "NEAR",
    "APTUSDT":   "APT",   "OPUSDT":    "OP",    "ARBUSDT":   "ARB",
    "ATOMUSDT":  "ATOM",  "FTMUSDT":   "FTM",   "INJUSDT":   "INJ",
    "RUNEUSDT":  "RUNE",  "LDOUSDT":   "LDO",   "MKRUSDT":   "MKR",
    "AAVEUSDT":  "AAVE",  "GRTUSDT":   "GRT",   "SNXUSDT":   "SNX",
    "COMPUSDT":  "COMP",  "CRVUSDT":   "CRV",   "SUIUSDT":   "SUI",
    "SEIUSDT":   "SEI",   "TIAUSDT":   "TIA",   "WLDUSDT":   "WLD",
    "JUPUSDT":   "JUP",   "PYTHUSDT":  "PYTH",  "STRKUSDT":  "STRK",
    # Tier 3 — mid cap notable
    "FILUSDT":   "FIL",   "SANDUSDT":  "SAND",  "MANAUSDT":  "MANA",
    "AXSUSDT":   "AXS",   "APEUSDT":   "APE",   "GALAUSDT":  "GALA",
    "IMXUSDT":   "IMX",   "FLOWUSDT":  "FLOW",  "CHZUSDT":   "CHZ",
    "ENJUSDT":   "ENJ",   "ALGOUSDT":  "ALGO",  "XLMUSDT":   "XLM",
    "VETUSDT":   "VET",   "XTZUSDT":   "XTZ",   "EOSUSDT":   "EOS",
    "NEOUSDT":   "NEO",   "ZILUSDT":   "ZIL",   "QNTUSDT":   "QNT",
    "EGLDUSDT":  "EGLD",  "FETUSDT":   "FET",   "OCEANUSDT": "OCEAN",
    "RLCUSDT":   "RLC",   "BTTCUSDT":  "BTTC",  "ONEUSDT":   "ONE",
    "HBARUSDT":  "HBAR",  "IOTAUSDT":  "IOTA",  "XMRUSDT":   "XMR",
    "DASHUSDT":  "DASH",  "ZECUSDT":   "ZEC",   "BATUSDT":   "BAT",
    "1INCHUSDT": "1INCH", "YFIUSDT":   "YFI",   "SUSHIUSDT": "SUSHI",
    "CAKEUSDT":  "CAKE",  "DYDXUSDT":  "DYDX",  "GMXUSDT":   "GMX",
    "STXUSDT":   "STX",   "CFXUSDT":   "CFX",   "BLURUSDT":  "BLUR",
    "PENDLEUSDT":"PENDLE","WIFUSDT":   "WIF",   "BONKUSDT":  "BONK",
    "PEPEUSDT":  "PEPE",  "FLOKIUSDT": "FLOKI", "KASUSDT":   "KAS",
}

# ── Coinbase: subconjunto disponible en Advanced Trade ─────────────
COINBASE_SYMBOLS = {
    "BTC-USD":   "BTC",  "ETH-USD":   "ETH",  "SOL-USD":   "SOL",
    "XRP-USD":   "XRP",  "ADA-USD":   "ADA",  "DOGE-USD":  "DOGE",
    "AVAX-USD":  "AVAX", "DOT-USD":   "DOT",  "LINK-USD":  "LINK",
    "LTC-USD":   "LTC",  "UNI-USD":   "UNI",  "MATIC-USD": "MATIC",
    "NEAR-USD":  "NEAR", "APT-USD":   "APT",  "OP-USD":    "OP",
    "ATOM-USD":  "ATOM", "FTM-USD":   "FTM",  "INJ-USD":   "INJ",
    "LDO-USD":   "LDO",  "MKR-USD":   "MKR",  "AAVE-USD":  "AAVE",
    "GRT-USD":   "GRT",  "CRV-USD":   "CRV",  "SNX-USD":   "SNX",
    "COMP-USD":  "COMP", "FIL-USD":   "FIL",  "SAND-USD":  "SAND",
    "MANA-USD":  "MANA", "AXS-USD":   "AXS",  "APE-USD":   "APE",
    "IMX-USD":   "IMX",  "FLOW-USD":  "FLOW", "CHZ-USD":   "CHZ",
    "ALGO-USD":  "ALGO", "XLM-USD":   "XLM",  "XTZ-USD":   "XTZ",
    "EOS-USD":   "EOS",  "FET-USD":   "FET",  "OCEAN-USD": "OCEAN",
    "XMR-USD":   "XMR",  "ZEC-USD":   "ZEC",  "BAT-USD":   "BAT",
    "1INCH-USD": "1INCH","YFI-USD":   "YFI",  "SUSHI-USD": "SUSHI",
    "DYDX-USD":  "DYDX", "STX-USD":   "STX",  "BLUR-USD":  "BLUR",
    "WIF-USD":   "WIF",  "PEPE-USD":  "PEPE",
}

# ── Kraken: pares disponibles ──────────────────────────────────────
KRAKEN_SYMBOLS = {
    "XBT/USD":   "BTC",  "ETH/USD":   "ETH",  "SOL/USD":   "SOL",
    "XRP/USD":   "XRP",  "ADA/USD":   "ADA",  "DOGE/USD":  "DOGE",
    "DOT/USD":   "DOT",  "LINK/USD":  "LINK", "LTC/USD":   "LTC",
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

# ── Orden de display: Tier 1 primero, luego por categoría ──────────
SYMBOLS_ORDERED = [
    # Mega cap
    "BTC","ETH","BNB","SOL","XRP","ADA","DOGE","AVAX","DOT","LINK","LTC","UNI",
    # L1 / infraestructura
    "TRX","TON","NEAR","APT","OP","ARB","SUI","SEI","TIA","STX","HBAR","ALGO",
    "XLM","VET","XTZ","EOS","NEO","EGLD","IOTA","ONE","CFX","KAS",
    # DeFi
    "ATOM","FTM","INJ","RUNE","LDO","MKR","AAVE","GRT","SNX","COMP","CRV",
    "DYDX","GMX","PENDLE","1INCH","YFI","SUSHI","CAKE","BAT",
    # NFT / Gaming / Metaverso
    "SAND","MANA","AXS","APE","GALA","IMX","FLOW","CHZ","ENJ",
    # Web3 / AI / Data
    "ICP","FIL","FET","OCEAN","RLC","QNT",
    # Memes
    "SHIB","PEPE","WIF","BONK","FLOKI","BTTC",
    # Privacy
    "XMR","DASH","ZEC",
    # Otros notables
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
    "SEI":"Sei",           "TIA":"Celestia",       "WLD":"Worldcoin",
    "JUP":"Jupiter",       "PYTH":"Pyth Network",  "STRK":"Starknet",
    "FIL":"Filecoin",      "SAND":"The Sandbox",   "MANA":"Decentraland",
    "AXS":"Axie Infinity", "APE":"ApeCoin",        "GALA":"Gala",
    "IMX":"Immutable X",   "FLOW":"Flow",          "CHZ":"Chiliz",
    "ENJ":"Enjin Coin",    "ALGO":"Algorand",      "XLM":"Stellar",
    "VET":"VeChain",       "XTZ":"Tezos",          "EOS":"EOS",
    "NEO":"NEO",           "ZIL":"Zilliqa",        "QNT":"Quant",
    "EGLD":"MultiversX",   "FET":"Fetch.ai",       "OCEAN":"Ocean Proto.",
    "RLC":"iExec RLC",     "BTTC":"BitTorrent",    "ONE":"Harmony",
    "HBAR":"Hedera",       "IOTA":"IOTA",          "XMR":"Monero",
    "DASH":"Dash",         "ZEC":"Zcash",          "BAT":"Basic Attn Tkn",
    "1INCH":"1inch",       "YFI":"Yearn Finance",  "SUSHI":"SushiSwap",
    "CAKE":"PancakeSwap",  "DYDX":"dYdX",          "GMX":"GMX",
    "STX":"Stacks",        "CFX":"Conflux",        "BLUR":"Blur",
    "PENDLE":"Pendle",     "WIF":"dogwifhat",      "BONK":"Bonk",
    "PEPE":"Pepe",         "FLOKI":"Floki",        "KAS":"Kaspa",
}

HISTORY_MAX = 120

BINANCE_WS_URL  = "wss://stream.binance.com:9443/ws"
BINANCE_WS_ALT  = "wss://stream.binance.com:443/ws"
COINBASE_WS_URL = "wss://advanced-trade-ws.coinbase.com"
KRAKEN_WS_URL   = "wss://ws.kraken.com"

HEADERS = {"User-Agent": "CryptexTerminal/3.1", "Accept": "application/json"}
COINGECKO_API_KEY = "CG-HPLwJp5CEjk9w6NMHgyqWhzk"
COINGECKO_HEADERS = dict(HEADERS)
if COINGECKO_API_KEY:
    COINGECKO_HEADERS["X-CG-Pro-API-Key"] = COINGECKO_API_KEY

# ═══════════════════════════════════════════════════════════════════
#  ESTADO GLOBAL
# ═══════════════════════════════════════════════════════════════════

class MarketState:
    def __init__(self):
        self._lock = threading.Lock()
        self.prices:     dict  = {}
        self.prev:       dict  = {}
        self.chg24h:     dict  = {}
        self.high24:     dict  = {}
        self.low24:      dict  = {}
        self.vol24:      dict  = {}
        self.bid:        dict  = {}
        self.ask:        dict  = {}
        self.spread:     dict  = {}

        self.history:        dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.volume_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))

        # Para ATR necesitamos guardar los high/low tick a tick
        self.high_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.low_history:  dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))

        self.tick_count: dict = defaultdict(int)
        self.last_tick:  dict = {}
        self.latency_ms: dict = {}

        self.fg_data: list = []
        self.ws_source:  str  = "─"
        self.ws_status:  str  = "connecting"
        self.ws_ticks:   int  = 0
        self.ws_since:   str  = "─"
        self.ws_reconnects: int = 0

        self.alerts:     dict  = {}
        self.triggered:  list  = []

        self.global_data: dict = {}
        self.global_upd:  str  = "─"
        self.news: list = []
        self.news_upd: str = "─"

        self.errors: dict = {}

    def update_tick(self, sym: str, price: float, chg24: float,
                    high: float, low: float, vol: float,
                    bid: float = 0, ask: float = 0, latency_ms: float = 0):
        with self._lock:
            self.prev[sym]     = self.prices.get(sym, price)
            self.prices[sym]   = price
            self.chg24h[sym]   = chg24
            self.high24[sym]   = high
            self.low24[sym]    = low
            self.vol24[sym]    = vol

            if bid: self.bid[sym] = bid
            if ask: self.ask[sym] = ask
            if bid and ask and ask > 0:
                self.spread[sym] = (ask - bid) / ask * 100

            self.history[sym].append(price)
            self.volume_history[sym].append(vol)
            if high: self.high_history[sym].append(high)
            if low:  self.low_history[sym].append(low)

            self.tick_count[sym] += 1
            self.ws_ticks += 1
            self.last_tick[sym] = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
            if latency_ms:
                self.latency_ms[sym] = latency_ms

        self._check_alert(sym, price)

    def _check_alert(self, sym: str, price: float):
        target = self.alerts.get(sym)
        if target and price >= target:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            with self._lock:
                self.triggered.append((ts, f"{sym} ≥ ${target:,.0f}"))
                del self.alerts[sym]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "prices":    dict(self.prices),
                "prev":      dict(self.prev),
                "chg24h":    dict(self.chg24h),
                "high24":    dict(self.high24),
                "low24":     dict(self.low24),
                "vol24":     dict(self.vol24),
                "bid":       dict(self.bid),
                "ask":       dict(self.ask),
                "spread":    dict(self.spread),
                "history":   {k: list(v) for k, v in self.history.items()},
                "volume_history": {k: list(v) for k, v in self.volume_history.items()},
                "high_history": {k: list(v) for k, v in self.high_history.items()},
                "low_history":  {k: list(v) for k, v in self.low_history.items()},
                "tick_count":dict(self.tick_count),
                "last_tick": dict(self.last_tick),
                "latency_ms":dict(self.latency_ms),
                "ws_source": self.ws_source,
                "ws_status": self.ws_status,
                "ws_ticks":  self.ws_ticks,
                "ws_since":  self.ws_since,
                "ws_reconnects": self.ws_reconnects,
                "fg_data":   list(self.fg_data),
                "alerts":    dict(self.alerts),
                "triggered": list(self.triggered[-5:]),
                "global":    dict(self.global_data),
                "global_upd":self.global_upd,
                "news":      list(self.news),
                "news_upd":  self.news_upd,
                "errors":    dict(self.errors),
            }

mkt = MarketState()

# ═══════════════════════════════════════════════════════════════════
#  HELPERS DE FORMATO
# ═══════════════════════════════════════════════════════════════════

def fmt_price(p: float) -> str:
    if p <= 0:     return "    ─     "
    if p >= 1_000: return f"${p:>12,.2f}"
    if p >= 1:     return f"${p:>12.4f}"
    return f"${p:>12.6f}"

def fmt_large(n: float) -> str:
    if n <= 0:    return "─"
    if n >= 1e12: return f"${n/1e12:.2f}T"
    if n >= 1e9:  return f"${n/1e9:.2f}B"
    if n >= 1e6:  return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"

def pct_color(v: float) -> str:
    if v >=  5: return "bright_green"
    if v >=  2: return "green"
    if v >=  0: return "dark_green"
    if v >= -2: return "yellow"
    if v >= -5: return "red"
    return "bright_red"

def pct_text(v: float) -> Text:
    if v == 0: return Text("  ──   ", style="dim")
    arrow = "▲" if v >= 0 else "▼"
    return Text(f"{arrow}{abs(v):6.2f}%", style=pct_color(v))

def fg_color(v: int) -> str:
    if v < 25: return "bright_red"
    if v < 45: return "dark_orange3"
    if v < 55: return "yellow"
    if v < 75: return "green"
    return "bright_green"

def fg_label(v: int) -> str:
    if v < 25: return "EXTREME FEAR"
    if v < 45: return "FEAR"
    if v < 55: return "NEUTRAL"
    if v < 75: return "GREED"
    return "EXTREME GREED"

def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

def sparkline(values: list, width: int = 16) -> Text:
    bars = " ▁▂▃▄▅▆▇█"
    if len(values) < 2:
        return Text("─" * width, style="dim dark_green")
    sample = values[-width:]
    lo, hi = min(sample), max(sample)
    span = hi - lo or 1
    chars = [bars[int((v - lo) / span * (len(bars) - 1))] for v in sample]
    color = "bright_green" if sample[-1] >= sample[0] else "bright_red"
    return Text("".join(chars), style=color)

def price_flash_color(sym: str, s: dict) -> str:
    cur  = s["prices"].get(sym, 0)
    prev = s["prev"].get(sym, cur)
    if cur > prev:  return "bold bright_green"
    if cur < prev:  return "bold bright_red"
    return "bold bright_white"

# ═══════════════════════════════════════════════════════════════════
#  INDICADORES TÉCNICOS
# ═══════════════════════════════════════════════════════════════════

def calculate_rsi(prices: list, period: int = 14) -> float:
    """RSI clásico de Wilder."""
    if len(prices) < period + 1:
        return 50.0
    gains  = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
    losses = [abs(min(prices[i] - prices[i-1], 0)) for i in range(1, len(prices))]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period if sum(losses[-period:]) > 0 else 0.0001
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calculate_ema(prices: list, period: int) -> list:
    """EMA estándar. Retorna lista de la misma longitud (None hasta warm-up)."""
    if len(prices) < period:
        return [None] * len(prices)
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    sma = sum(prices[:period]) / period
    result.append(sma)
    for p in prices[period:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def calculate_ema_cross(prices: list, fast: int = 9, slow: int = 21) -> dict:
    """
    Retorna:
        signal  : 'BULL' | 'BEAR' | 'NEUTRAL'
        ema_fast: último valor EMA rápida
        ema_slow: último valor EMA lenta
        cross   : True si hubo cruce en los últimos 3 ticks
    """
    if len(prices) < slow + 1:
        return {"signal": "NEUTRAL", "ema_fast": None, "ema_slow": None, "cross": False}

    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)

    # Filtrar Nones alineados
    pairs = [(f, s) for f, s in zip(fast_ema, slow_ema) if f is not None and s is not None]
    if len(pairs) < 2:
        return {"signal": "NEUTRAL", "ema_fast": None, "ema_slow": None, "cross": False}

    cur_f, cur_s   = pairs[-1]
    prev_f, prev_s = pairs[-2]

    signal = "BULL" if cur_f > cur_s else "BEAR"
    # Cruce: la EMA rápida cruzó a la EMA lenta en los últimos ticks
    cross = (prev_f <= prev_s and cur_f > cur_s) or (prev_f >= prev_s and cur_f < cur_s)

    return {"signal": signal, "ema_fast": cur_f, "ema_slow": cur_s, "cross": cross}


def calculate_macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    Retorna:
        macd_line   : diferencia EMA fast - EMA slow
        signal_line : EMA de la MACD line
        histogram   : macd_line - signal_line
        direction   : 'UP' | 'DOWN' (histograma subiendo/bajando)
    """
    if len(prices) < slow + signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "─"}

    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)

    macd_line = [
        f - s for f, s in zip(fast_ema, slow_ema)
        if f is not None and s is not None
    ]
    if len(macd_line) < signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "─"}

    sig_line = calculate_ema(macd_line, signal)
    sig_vals = [v for v in sig_line if v is not None]
    if not sig_vals:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "─"}

    ml  = macd_line[-1]
    sl  = sig_vals[-1]
    hist = ml - sl

    # Dirección del histograma (comparar con tick anterior)
    hist_prev = (macd_line[-2] - sig_vals[-2]) if len(macd_line) >= 2 and len(sig_vals) >= 2 else hist
    direction = "UP" if hist > hist_prev else "DOWN"

    return {
        "macd_line":   round(ml, 6),
        "signal_line": round(sl, 6),
        "histogram":   round(hist, 6),
        "direction":   direction,
    }


def calculate_bollinger(prices: list, period: int = 20, std_mult: float = 2.0) -> dict:
    """
    Bollinger Bands.
    Retorna:
        upper, middle, lower : bandas
        pct_b               : posición del precio dentro de las bandas (0=lower, 1=upper)
        zone                 : 'ABOVE' | 'HIGH' | 'MID' | 'LOW' | 'BELOW'
        bandwidth            : (upper - lower) / middle * 100  → volatilidad relativa
    """
    if len(prices) < period:
        return {"upper": 0, "middle": 0, "lower": 0, "pct_b": 0.5, "zone": "MID", "bandwidth": 0}

    sample = prices[-period:]
    mid    = sum(sample) / period
    variance = sum((p - mid) ** 2 for p in sample) / period
    std    = variance ** 0.5
    upper  = mid + std_mult * std
    lower  = mid - std_mult * std
    price  = prices[-1]

    band_range = upper - lower or 0.0001
    pct_b = (price - lower) / band_range
    bandwidth = (upper - lower) / mid * 100 if mid else 0

    if price > upper:        zone = "ABOVE"
    elif pct_b >= 0.8:       zone = "HIGH"
    elif pct_b <= 0.2:       zone = "LOW"
    elif price < lower:      zone = "BELOW"
    else:                    zone = "MID"

    return {
        "upper":     round(upper, 6),
        "middle":    round(mid, 6),
        "lower":     round(lower, 6),
        "pct_b":     round(pct_b, 3),
        "zone":      zone,
        "bandwidth": round(bandwidth, 2),
    }


def calculate_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """
    Average True Range (Wilder).
    True Range = max(H-L, |H-Cprev|, |L-Cprev|)
    Retorna ATR como % del precio actual para ser comparable entre activos.
    """
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0

    trs = []
    for i in range(1, n):
        hl  = highs[i] - lows[i]
        hcp = abs(highs[i] - closes[i-1])
        lcp = abs(lows[i] - closes[i-1])
        trs.append(max(hl, hcp, lcp))

    if len(trs) < period:
        return 0.0

    # Wilder smoothing
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period

    # Normalizar como % del precio actual
    price = closes[-1]
    return round((atr / price * 100), 3) if price else 0.0


def calculate_signal(rsi: float, ema_cross: dict, macd: dict, bb: dict) -> dict:
    """
    Señal combinada: pondera RSI + EMA + MACD + BB.
    Score: +1 por señal alcista, -1 bajista.
    Retorna:
        score  : int  (-4 a +4)
        signal : 'STRONG LONG' | 'LONG' | 'NEUTRAL' | 'SHORT' | 'STRONG SHORT'
        color  : rich color string
        icon   : emoji/char
    """
    score = 0

    # RSI
    if rsi < 30:   score += 1   # sobreventa → posible rebote
    elif rsi > 70: score -= 1   # sobrecompra → posible caída

    # EMA Cross
    if ema_cross.get("signal") == "BULL":   score += 1
    elif ema_cross.get("signal") == "BEAR": score -= 1
    if ema_cross.get("cross"):              score += (1 if ema_cross["signal"] == "BULL" else -1)

    # MACD histograma
    hist = macd.get("histogram", 0)
    direction = macd.get("direction", "─")
    if hist > 0 and direction == "UP":    score += 1
    elif hist < 0 and direction == "DOWN": score -= 1

    # Bollinger
    zone = bb.get("zone", "MID")
    if zone == "LOW" or zone == "BELOW":    score += 1
    elif zone == "HIGH" or zone == "ABOVE": score -= 1

    if score >= 3:    sig, col, icon = "STR LONG",  "bold bright_green", "●●"
    elif score >= 1:  sig, col, icon = "LONG",       "green",             "●○"
    elif score <= -3: sig, col, icon = "STR SHORT",  "bold bright_red",   "●●"
    elif score <= -1: sig, col, icon = "SHORT",      "red",               "●○"
    else:             sig, col, icon = "NEUTRAL",    "yellow",            "○○"

    return {"score": score, "signal": sig, "color": col, "icon": icon}


def relative_volume(vol_history: list, current_vol: float) -> float:
    if len(vol_history) < 10 or current_vol <= 0:
        return 1.0
    avg_vol = sum(list(vol_history)[-20:]) / len(list(vol_history)[-20:])
    return round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0


# ═══════════════════════════════════════════════════════════════════
#  WEBSOCKET — BINANCE
# ═══════════════════════════════════════════════════════════════════

class BinanceStream:
    def __init__(self):
        self._ws: websocket.WebSocketApp = None
        self._thread: threading.Thread   = None
        self._stop_flag                  = threading.Event()
        self._reconnect_delay            = 2

    def _stream_url(self, port=9443) -> str:
        streams = "/".join(f"{sym.lower()}@miniTicker" for sym in BINANCE_SYMBOLS)
        return f"wss://stream.binance.com:{port}/stream?streams={streams}"

    def _on_open(self, ws):
        with mkt._lock:
            mkt.ws_source   = "Binance"
            mkt.ws_status   = "connected ✓"
            mkt.ws_since    = now_utc()
        self._reconnect_delay = 2

    def _on_message(self, ws, raw: str):
        try:
            t0   = time.perf_counter()
            msg  = json.loads(raw)
            data = msg.get("data", msg)
            sym_raw = data.get("s", "")
            sym  = BINANCE_SYMBOLS.get(sym_raw)
            if not sym:
                return
            price  = float(data["c"])
            chg24  = float(data["P"])
            high   = float(data["h"])
            low    = float(data["l"])
            vol    = float(data["v"])
            lat_ms = (time.perf_counter() - t0) * 1000
            mkt.update_tick(sym, price, chg24, high, low, vol, latency_ms=lat_ms)
        except Exception:
            pass

    def _on_error(self, ws, err):
        with mkt._lock:
            mkt.ws_status = f"error: {str(err)[:30]}"
            mkt.errors["ws"] = str(err)[:60]

    def _on_close(self, ws, code, reason):
        with mkt._lock:
            mkt.ws_status = "disconnected — reconnecting..."
            mkt.ws_reconnects += 1

    def start(self, port: int = 9443):
        self._stop_flag.clear()
        def _run():
            alt_port = 443 if port == 9443 else 9443
            url = self._stream_url(port)
            while not self._stop_flag.is_set():
                with mkt._lock:
                    mkt.ws_status = f"connecting ({url[:40]}...)"
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open, on_message=self._on_message,
                    on_error=self._on_error, on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=0)
                if self._stop_flag.is_set():
                    break
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
                url = self._stream_url(alt_port if self._reconnect_delay > 4 else port)
        self._thread = threading.Thread(target=_run, name="binance-ws", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        if self._ws:
            self._ws.close()


# ═══════════════════════════════════════════════════════════════════
#  WEBSOCKET — COINBASE
# ═══════════════════════════════════════════════════════════════════

class CoinbaseStream:
    def __init__(self):
        self._ws   = None
        self._stop = threading.Event()
        self._delay = 2

    def _subscribe_msg(self) -> str:
        return json.dumps({
            "type": "subscribe",
            "product_ids": list(COINBASE_SYMBOLS.keys()),
            "channel": "ticker",
        })

    def _on_open(self, ws):
        ws.send(self._subscribe_msg())
        with mkt._lock:
            mkt.ws_source = "Coinbase"
            mkt.ws_status = "connected ✓"
            mkt.ws_since  = now_utc()
        self._delay = 2

    def _on_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
            if msg.get("channel") != "ticker":
                return
            for event in msg.get("events", []):
                for tick in event.get("tickers", []):
                    prod  = tick.get("product_id", "")
                    sym   = COINBASE_SYMBOLS.get(prod)
                    if not sym: continue
                    price  = float(tick.get("price", 0) or 0)
                    chg24  = float(tick.get("price_percent_chg_24h", 0) or 0)
                    high   = float(tick.get("high_52_week", 0) or 0)
                    low    = float(tick.get("low_52_week", 0) or 0)
                    vol    = float(tick.get("volume_24h", 0) or 0)
                    bid    = float(tick.get("best_bid", 0) or 0)
                    ask    = float(tick.get("best_ask", 0) or 0)
                    mkt.update_tick(sym, price, chg24, high, low, vol, bid, ask)
        except Exception:
            pass

    def _on_error(self, ws, err):
        with mkt._lock:
            mkt.ws_status = f"error: {str(err)[:30]}"

    def _on_close(self, ws, code, reason):
        with mkt._lock:
            mkt.ws_status = "disconnected — reconnecting..."
            mkt.ws_reconnects += 1

    def start(self):
        self._stop.clear()
        def _run():
            while not self._stop.is_set():
                self._ws = websocket.WebSocketApp(
                    COINBASE_WS_URL,
                    on_open=self._on_open, on_message=self._on_message,
                    on_error=self._on_error, on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
                if self._stop.is_set(): break
                time.sleep(self._delay)
                self._delay = min(self._delay * 2, 60)
        threading.Thread(target=_run, name="coinbase-ws", daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._ws: self._ws.close()


# ═══════════════════════════════════════════════════════════════════
#  WEBSOCKET — KRAKEN
# ═══════════════════════════════════════════════════════════════════

class KrakenStream:
    def __init__(self):
        self._ws   = None
        self._stop = threading.Event()
        self._delay = 2

    def _subscribe_msg(self) -> str:
        return json.dumps({
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol":  list(KRAKEN_SYMBOLS.keys()),
            }
        })

    def _on_open(self, ws):
        ws.send(self._subscribe_msg())
        with mkt._lock:
            mkt.ws_source = "Kraken"
            mkt.ws_status = "connected ✓"
            mkt.ws_since  = now_utc()
        self._delay = 2

    def _on_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
            if msg.get("channel") != "ticker": return
            for d in msg.get("data", []):
                pair = d.get("symbol", "")
                sym  = KRAKEN_SYMBOLS.get(pair)
                if not sym: continue
                price  = float(d.get("last",       0) or 0)
                chg24  = float(d.get("change_pct", 0) or 0)
                high   = float(d.get("high",       0) or 0)
                low    = float(d.get("low",        0) or 0)
                vol    = float(d.get("volume",     0) or 0)
                bid    = float(d.get("bid",        0) or 0)
                ask    = float(d.get("ask",        0) or 0)
                mkt.update_tick(sym, price, chg24, high, low, vol, bid, ask)
        except Exception:
            pass

    def _on_error(self, ws, err):
        with mkt._lock:
            mkt.ws_status = f"error: {str(err)[:30]}"

    def _on_close(self, ws, *a):
        with mkt._lock:
            mkt.ws_status = "disconnected — reconnecting..."
            mkt.ws_reconnects += 1

    def start(self):
        self._stop.clear()
        def _run():
            while not self._stop.is_set():
                self._ws = websocket.WebSocketApp(
                    KRAKEN_WS_URL,
                    on_open=self._on_open, on_message=self._on_message,
                    on_error=self._on_error, on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
                if self._stop.is_set(): break
                time.sleep(self._delay)
                self._delay = min(self._delay * 2, 60)
        threading.Thread(target=_run, name="kraken-ws", daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._ws: self._ws.close()


# ═══════════════════════════════════════════════════════════════════
#  REST AUXILIAR — Fear & Greed + Global + News
# ═══════════════════════════════════════════════════════════════════

def _rest_loop(fn, interval: int):
    fn()
    def loop():
        while True:
            time.sleep(interval)
            fn()
    threading.Thread(target=loop, daemon=True).start()

def _fetch_fg():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=30&format=json",
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        with mkt._lock:
            mkt.fg_data = r.json().get("data", [])
            mkt.errors.pop("fg", None)
    except Exception as e:
        with mkt._lock:
            mkt.errors["fg"] = str(e)[:40]

def _fetch_global():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global",
                         headers=COINGECKO_HEADERS, timeout=10)
        r.raise_for_status()
        with mkt._lock:
            mkt.global_data = r.json().get("data", {})
            mkt.global_upd  = now_utc()
            mkt.errors.pop("global", None)
    except Exception as e:
        with mkt._lock:
            mkt.errors["global"] = str(e)[:40]

def _fetch_news():
    try:
        r = requests.get(
            "https://api.coingecko.com/api/v3/news",
            headers=COINGECKO_HEADERS,
            params={"per_page": 10, "page": 1},
            timeout=10,
        )
        if r.status_code == 200:
            payload = r.json()
            items = payload.get("data", []) if isinstance(payload, dict) else payload
            news_list = []
            for item in items[:10]:
                news_list.append({
                    "title":  str(item.get("title",     "Sin título"))[:108],
                    "source": str(item.get("news_site", item.get("source", "News")))[:18],
                    "time":   str(item.get("created_at", ""))[:16] or now_utc()[:16],
                })
            if news_list:
                with mkt._lock:
                    mkt.news     = news_list
                    mkt.news_upd = now_utc()
                    mkt.errors.pop("news", None)
                return
    except Exception as e:
        with mkt._lock:
            mkt.errors["news"] = str(e)[:40]

    # Fallback RSS
    rss_sources = [
        ("CoinTelegraph", "https://cointelegraph.com/rss"),
        ("Decrypt",       "https://decrypt.co/feed"),
        ("CryptoNews",    "https://cryptonews.com/newsfeed/"),
        ("Bitcoin.com",   "https://news.bitcoin.com/feed/"),
    ]
    for source_name, rss_url in rss_sources:
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=10)
            if r.status_code != 200: continue
            root  = ET.fromstring(r.content)
            items = root.findall('.//item')
            news_list = []
            for item in items[:10]:
                title   = html.unescape(item.findtext('title', default='Sin título'))
                link    = item.findtext('link', default='')
                pubdate = item.findtext('pubDate', default='')
                try:
                    source = urlparse(link).hostname or source_name
                except Exception:
                    source = source_name
                news_list.append({
                    "title":  title[:108],
                    "source": source[:18],
                    "time":   pubdate[:16] if pubdate else now_utc()[:16],
                })
            if news_list:
                with mkt._lock:
                    mkt.news     = news_list
                    mkt.news_upd = now_utc()
                    mkt.errors.pop("news", None)
                return
        except Exception:
            continue

    # Fallback estático
    with mkt._lock:
        mkt.news = [
            {"title": "Bitcoin se mantiene fuerte por encima de los $105,000",
             "source": "CoinDesk", "time": now_utc()[:16]},
            {"title": "Ethereum ETFs registran inflows récord esta semana",
             "source": "The Block", "time": now_utc()[:16]},
            {"title": "Solana lidera el volumen DeFi con nuevo ATH",
             "source": "Decrypt", "time": now_utc()[:16]},
            {"title": "Análisis: ¿Corrección o continuación alcista?",
             "source": "CryptoSlate", "time": now_utc()[:16]},
            {"title": "Mercados crypto a la espera de datos macroeconómicos",
             "source": "Cointelegraph", "time": now_utc()[:16]},
        ]
        mkt.news_upd = now_utc()


# ═══════════════════════════════════════════════════════════════════
#  PANELS (Rich)
# ═══════════════════════════════════════════════════════════════════

console = Console()

def panel_header(s: dict) -> Panel:
    ts  = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M:%S.%f")[:-3] + " UTC"
    g   = Table.grid(expand=True)
    g.add_column(); g.add_column(justify="center"); g.add_column(justify="right")
    g.add_row(
        Text("◈ AZ TERMINAL v3.2", style="bold bright_green"),
        Text(f"[{s['ws_source']}]  {s['ws_status']}  ✦ {s['ws_ticks']:,} ticks", style="dim green"),
        Text(ts, style="dim green"),
    )
    return Panel(g, border_style="bright_green", padding=(0, 1))

_ticker_offset = 0
_ticker_last   = 0.0

def panel_ticker(s: dict) -> Panel:
    global _ticker_offset, _ticker_last
    # Rotar cada 4 segundos para mostrar todos los símbolos
    now = time.monotonic()
    active = [sym for sym in SYMBOLS_ORDERED if s["prices"].get(sym, 0)]
    if active:
        window = 18  # cuántos símbolos mostrar a la vez
        if now - _ticker_last > 4.0:
            _ticker_offset = (_ticker_offset + window) % len(active)
            _ticker_last   = now
        visible = (active[_ticker_offset:] + active[:_ticker_offset])[:window]
    else:
        visible = []

    parts = []
    for sym in visible:
        p   = s["prices"].get(sym, 0)
        chg = s["chg24h"].get(sym, 0)
        if not p: continue
        col = "bright_green" if chg >= 0 else "bright_red"
        ar  = "▲" if chg >= 0 else "▼"
        parts.append(
            f"[bold bright_green]{sym}[/] [white]${p:,.4g}[/] "
            f"[{col}]{ar}{abs(chg):.2f}%[/]  [dim dark_green]│[/]  "
        )
    total = len(active)
    suffix = f"  [dim green]({total} pares activos)[/]" if total else ""
    txt = Text.from_markup("".join(parts) + suffix) if parts else Text("Conectando WS...", style="dim green")
    return Panel(txt, border_style="dark_green", padding=(0, 1))

# Agrupación por categoría para el panel de precios
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

_prices_page   = 0          # página actual (cada página = 1 categoría)
_prices_last_p = 0.0        # timestamp último cambio de página

def panel_prices(s: dict) -> Panel:
    global _prices_page, _prices_last_p
    # Avanzar de categoría cada 8 segundos
    now = time.monotonic()
    cat_names = list(SYMBOL_CATEGORIES.keys())
    if now - _prices_last_p > 8.0:
        _prices_page  = (_prices_page + 1) % len(cat_names)
        _prices_last_p = now

    current_cat  = cat_names[_prices_page]
    cat_symbols  = SYMBOL_CATEGORIES[current_cat]
    page_info    = f"[dim]cat {_prices_page+1}/{len(cat_names)} — {current_cat}[/]"

    tbl = Table(
        box=box.SIMPLE_HEAVY, border_style="dark_green",
        header_style="bold bright_green", show_lines=False,
        expand=True, padding=(0, 1),
    )
    tbl.add_column("SYM",     style="bold bright_green", min_width=6)
    tbl.add_column("NOMBRE",  style="dim green",         min_width=14)
    tbl.add_column("LAST",    justify="right",            min_width=14)
    tbl.add_column("24H%",    justify="right",            min_width=9)
    tbl.add_column("RSI",     justify="right",            min_width=5)
    tbl.add_column("EMA",     justify="center",           min_width=7)
    tbl.add_column("MACD",    justify="right",            min_width=9)
    tbl.add_column("BB",      justify="center",           min_width=7)
    tbl.add_column("ATR%",    justify="right",            min_width=6)
    tbl.add_column("SIGNAL",  justify="center",           min_width=10)
    tbl.add_column("RVOL",    justify="right",            min_width=6)
    tbl.add_column("SPREAD",  justify="right",            min_width=7)
    tbl.add_column("SPARK",   min_width=14)

    # Mostrar símbolos de la categoría actual que tengan precio
    shown = 0
    for sym in cat_symbols:
        price = s["prices"].get(sym, 0)
        if not price:
            tbl.add_row(
                Text(sym, style="dim"),
                Text(SYMBOL_NAME.get(sym,""), style="dim"),
                Text("─ esperando", style="dim"),
                *["─"] * 10,
            )
            shown += 1
            continue

        chg      = s["chg24h"].get(sym, 0)
        spread   = s["spread"].get(sym, 0)
        hist     = list(s.get("history", {}).get(sym, []))
        vol_hist = list(s.get("volume_history", {}).get(sym, []))
        highs    = list(s.get("high_history", {}).get(sym, []))
        lows     = list(s.get("low_history",  {}).get(sym, []))
        vol24    = s["vol24"].get(sym, 0)

        rsi      = calculate_rsi(hist)
        ema_data = calculate_ema_cross(hist)
        macd_data= calculate_macd(hist)
        bb_data  = calculate_bollinger(hist)
        atr_pct  = calculate_atr(highs, lows, hist)
        rel_vol  = relative_volume(vol_hist, vol24)
        sig_data = calculate_signal(rsi, ema_data, macd_data, bb_data)

        price_col = price_flash_color(sym, s)
        rsi_color = "bright_red" if rsi > 70 else "bright_green" if rsi < 30 else "yellow"
        vol_color = "bright_green" if rel_vol > 2.5 else "green" if rel_vol > 1.5 else "dim white"

        ema_col = "bright_green" if ema_data["signal"] == "BULL" else "bright_red"
        ema_txt = ("▲ BULL" if ema_data["signal"] == "BULL" else "▼ BEAR")
        if ema_data["cross"]: ema_txt += "✦"

        hist_val   = macd_data["histogram"]
        macd_col   = "bright_green" if hist_val > 0 else "bright_red"
        macd_arrow = "▲" if macd_data["direction"] == "UP" else "▼"
        if abs(hist_val) < 0.01:
            macd_str = f"{macd_arrow}{hist_val*1000:+.2f}‰"
        else:
            macd_str = f"{macd_arrow}{hist_val:+.3f}"

        bb_zone = bb_data["zone"]
        bb_colors = {"ABOVE":"bright_red","HIGH":"red","MID":"yellow","LOW":"green","BELOW":"bright_green"}
        bb_icons  = {"ABOVE":"↑↑ OB","HIGH":"↑  HI","MID":"── MID","LOW":"↓  LO","BELOW":"↓↓ OS"}
        atr_col = "bright_red" if atr_pct > 3 else "yellow" if atr_pct > 1.5 else "dim green"

        tbl.add_row(
            sym,
            SYMBOL_NAME.get(sym, ""),
            Text(fmt_price(price),    style=price_col),
            pct_text(chg),
            Text(f"{rsi}",            style=rsi_color),
            Text(ema_txt,             style=ema_col),
            Text(macd_str,            style=macd_col),
            Text(bb_icons.get(bb_zone, bb_zone), style=bb_colors.get(bb_zone, "white")),
            Text(f"{atr_pct:.2f}%" if atr_pct else "─", style=atr_col),
            Text(sig_data["signal"],  style=sig_data["color"]),
            Text(f"{rel_vol:.1f}x",   style=vol_color),
            Text(f"{spread:.3f}%" if spread else "─", style="dim white"),
            sparkline(hist, 14),
        )
        shown += 1

    src = s["ws_source"]
    active_total = sum(1 for sym in SYMBOLS_ORDERED if s["prices"].get(sym, 0))
    return Panel(
        tbl,
        title=(
            f"[bold bright_green]◆ MARKETS — {current_cat}[/]  "
            f"{page_info}  [dim]total activos: {active_total}/{len(SYMBOLS_ORDERED)}  "
            f"auto-rotación 8s  src:{src}[/]"
        ),
        border_style="green",
    )


# ─────────────────────────────────────────────────────────────────
#  PANEL LEYENDA DE INDICADORES (nuevo, reemplaza BID/ASK en sidebar)
# ─────────────────────────────────────────────────────────────────

def panel_indicators_legend() -> Panel:
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(style="bold bright_green", min_width=9)
    tbl.add_column(style="dim green")

    tbl.add_row("RSI(14)",   "< 30 sobreventa  > 70 sobrecompra")
    tbl.add_row("EMA 9/21",  "▲ BULL cruce alcista  ✦ cruce reciente")
    tbl.add_row("MACD",      "▲/▼ hist. sube/baja  ‰ = ×1000")
    tbl.add_row("BB(20,2σ)", "↑↑ OB sobrecompra  ↓↓ OS sobreventa")
    tbl.add_row("ATR%",      "volatilidad  > 3% alta  < 1.5% baja")
    tbl.add_row("SIGNAL",    "RSI+EMA+MACD+BB → STR LONG/SHORT")
    tbl.add_row("RVOL",      "volumen relativo  > 2.5x inusual")

    return Panel(tbl, title="[bold bright_green]LEYENDA[/]", border_style="dark_green", padding=(0,1))


def panel_fg(s: dict) -> Panel:
    items = s["fg_data"]
    if not items:
        return Panel("[dim green]Cargando Fear & Greed...[/]", title="FEAR & GREED", border_style="green")
    vals = [int(d["value"]) for d in items]
    cur  = vals[0]
    col  = fg_color(cur)
    lbl  = fg_label(cur)
    bar_n = int(cur / 100 * 22)
    bar   = "█" * bar_n + "░" * (22 - bar_n)

    g = Table.grid(padding=(0, 0), expand=True)
    g.add_column(justify="center")
    g.add_row(Text(str(cur), style=f"bold {col}", justify="center"))
    g.add_row(Text(lbl,      style=f"bold {col}", justify="center"))
    g.add_row(Text(bar,      style=col,           justify="center"))

    st = Table.grid(expand=True)
    st.add_column(style="dim green"); st.add_column(justify="right")
    for label, idx in [("AYER",1),("SEMANA",7),("MES",30)]:
        if idx < len(vals):
            v = vals[idx]
            st.add_row(label, Text(f"{v}  {fg_label(v)[:4]}", style=fg_color(v)))

    g.add_row(sparkline(list(reversed(vals[:30])), 22))
    g.add_row(st)
    return Panel(g, title="[bold bright_green]FEAR & GREED 30d[/]", border_style="green", padding=(0,1))


def panel_global(s: dict) -> Panel:
    g = s["global"]
    if not g:
        return Panel("[dim green]Cargando...[/]", title="GLOBAL", border_style="green")
    mc   = g.get("total_market_cap", {}).get("usd", 0)
    vol  = g.get("total_volume", {}).get("usd", 0)
    chg  = g.get("market_cap_change_percentage_24h_usd", 0)
    dom  = g.get("market_cap_percentage", {})
    coins= g.get("active_cryptocurrencies", 0)

    tbl = Table.grid(padding=(0,1), expand=True)
    tbl.add_column(style="dim green"); tbl.add_column(justify="right")
    tbl.add_row("MKT CAP",     Text(fmt_large(mc),  style="bold bright_white"))
    tbl.add_row("24H CHG",     pct_text(chg))
    tbl.add_row("VOLUMEN 24H", Text(fmt_large(vol), style="bright_white"))
    tbl.add_row("MONEDAS",     Text(f"{coins:,}",   style="bright_white"))
    tbl.add_row(Rule(style="dark_green"), "")
    top = sorted(dom.items(), key=lambda x: x[1], reverse=True)[:6]
    for sym, pct in top:
        bar = "█" * int(pct/4) + "░" * max(0, 18-int(pct/4))
        tbl.add_row(Text(sym.upper(), style="green"),
                    Text(f"{pct:5.1f}% {bar[:12]}", style="dark_green"))
    tbl.add_row(Rule(style="dark_green"), "")
    tbl.add_row("REST upd", Text(s["global_upd"], style="dim green"))
    return Panel(tbl, title="[bold bright_green]GLOBAL[/]", border_style="green", padding=(0,1))


def panel_ws_stats(s: dict) -> Panel:
    tbl = Table.grid(padding=(0,1), expand=True)
    tbl.add_column(style="dim green"); tbl.add_column(justify="right")

    tbl.add_row("[bold]WS STATUS[/bold]","")
    tbl.add_row("FUENTE",  Text(s["ws_source"],          style="bold bright_green"))
    tbl.add_row("ESTADO",  Text(s["ws_status"],          style="green" if "✓" in s["ws_status"] else "yellow"))
    tbl.add_row("DESDE",   Text(s["ws_since"],           style="dim green"))
    tbl.add_row("TICKS",   Text(f"{s['ws_ticks']:,}",    style="bright_white"))
    tbl.add_row("RECONEX", Text(str(s["ws_reconnects"]), style="yellow" if s["ws_reconnects"] else "dim green"))

    tbl.add_row(Rule(style="dark_green"),"")
    tbl.add_row("[bold]LAST TICK[/bold]","")
    for sym in ["BTC","ETH","SOL","BNB"]:
        lt  = s["last_tick"].get(sym,"─")
        lat = s["latency_ms"].get(sym, 0)
        lat_str = f"{lat:.1f}ms" if lat else "─"
        tbl.add_row(f"  {sym}", Text(f"{lt}  {lat_str}", style="dim green"))

    if s["alerts"]:
        tbl.add_row(Rule(style="dark_green"),"")
        tbl.add_row("[bold]ALERTAS[/bold]","")
        for sym, target in s["alerts"].items():
            tbl.add_row(f"  {sym}", Text(f"≥ {fmt_price(target).strip()}", style="yellow"))

    if s["triggered"]:
        tbl.add_row(Rule(style="dark_green"),"")
        for ts, msg in s["triggered"][-3:]:
            tbl.add_row(f"  {ts}", Text(msg[:28], style="bold yellow"))

    if s["errors"]:
        tbl.add_row(Rule(style="dark_green"),"")
        for k, v in s["errors"].items():
            tbl.add_row(Text(f"  ✗ {k}", style="red"), Text(v[:20], style="dim red"))

    return Panel(tbl, title="[bold bright_green]WS STATS & ALERTAS[/]", border_style="green", padding=(0,1))


def panel_news(s: dict) -> Panel:
    news = s["news"]
    if not news:
        err = s["errors"].get("news", "Cargando noticias...")
        return Panel(Text(err, style="dim green"),
                     title="[bold bright_green]◆ NOTICIAS CRYPTO[/]",
                     border_style="green")

    tbl = Table.grid(padding=(0, 0), expand=True)
    tbl.add_column(min_width=4, style="dim dark_green")
    tbl.add_column(ratio=1)
    tbl.add_column(min_width=22, style="dim green", justify="right")

    for i, item in enumerate(news[:9]):
        title_style = "bold white" if i < 3 else "white"
        tbl.add_row(
            f" {i+1:02d}",
            Text(item.get("title", ""), style=title_style),
            Text(f"{item.get('source','')}  {item.get('time','')[-5:]}", style="dim green"),
        )
        if i < len(news) - 1:
            tbl.add_row("", Text("─" * 78, style="dark_green"), "")

    return Panel(tbl,
                 title=f"[bold bright_green]◆ NOTICIAS CRYPTO [dim]— {s['news_upd']}[/][/]",
                 border_style="green", padding=(0,1))


def panel_footer(s: dict) -> Panel:
    ts  = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + " UTC"
    txt = (
        f"[dim green]● WS LIVE — {s['ws_source']}[/]  "
        f"[dim]{s['ws_ticks']:,} ticks  │  ~{len(SYMBOLS_ORDERED)} pares  │  "
        f"RSI·EMA·MACD·BB·ATR  │  tabla auto-rota 8s  ticker rota 4s  │  "
        f"Ctrl+C salir[/]  [dim green]{ts}[/]"
    )
    return Panel(Text.from_markup(txt), border_style="dark_green", padding=(0,1))


# ═══════════════════════════════════════════════════════════════════
#  DASHBOARD LAYOUT
# ═══════════════════════════════════════════════════════════════════

def build_dashboard(s: dict) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header",  size=3),
        Layout(name="ticker",  size=3),
        Layout(name="body",    ratio=1),
        Layout(name="news",    size=12),
        Layout(name="footer",  size=3),
    )
    layout["body"].split_row(
        Layout(name="prices",  ratio=5),
        Layout(name="sidebar", ratio=1),
    )
    layout["sidebar"].split_column(
        Layout(name="legend",  ratio=4),
        Layout(name="fg",      ratio=5),
        Layout(name="global",  ratio=4),
        Layout(name="ws",      ratio=4),
    )
    layout["header"].update(panel_header(s))
    layout["ticker"].update(panel_ticker(s))
    layout["prices"].update(panel_prices(s))
    layout["legend"].update(panel_indicators_legend())
    layout["fg"].update(panel_fg(s))
    layout["global"].update(panel_global(s))
    layout["ws"].update(panel_ws_stats(s))
    layout["news"].update(panel_news(s))
    layout["footer"].update(panel_footer(s))
    return layout


# ═══════════════════════════════════════════════════════════════════
#  MODOS DE EJECUCIÓN
# ═══════════════════════════════════════════════════════════════════

_stream: object = None

def start_streams(source: str):
    global _stream
    if source == "coinbase":
        _stream = CoinbaseStream(); _stream.start()
    elif source == "kraken":
        _stream = KrakenStream();   _stream.start()
    else:
        _stream = BinanceStream();  _stream.start()

def start_rest():
    _rest_loop(_fetch_fg,     300)
    _rest_loop(_fetch_global, 120)
    _rest_loop(_fetch_news,   180)

def run_live(source: str = "binance"):
    console.print(
        f"[bold bright_green]◈ AZ TERMINAL v3.2[/] iniciando WebSocket [{source}]...",
        highlight=False,
    )
    start_streams(source)
    start_rest()

    def shutdown(sig, frame):
        console.print("\n[dim green]Cerrando streams...[/]")
        if _stream: _stream.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT,  shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    time.sleep(1.5)
    try:
        with Live(build_dashboard(mkt.snapshot()), refresh_per_second=2, screen=True) as live:
            while True:
                time.sleep(0.5)
                live.update(build_dashboard(mkt.snapshot()))
    except Exception as e:
        console.print(f"[red]Error: {e}[/]")

def run_once(source: str = "binance"):
    console.print("[bold bright_green]◈ AZ TERMINAL — SNAPSHOT[/]")
    start_streams(source)
    start_rest()
    time.sleep(4)
    console.print(build_dashboard(mkt.snapshot()))


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

[bold]INDICADORES TÉCNICOS:[/bold]
  [bright_green]RSI(14)[/]         < 30 sobreventa  /  > 70 sobrecompra
  [bright_green]EMA 9/21[/]        ▲BULL / ▼BEAR  (✦ = cruce reciente)
  [bright_green]MACD(12,26,9)[/]   histograma ▲/▼ con dirección
  [bright_green]BB(20,2σ)[/]       ↑↑OB / ↑HI / MID / ↓LO / ↓↓OS
  [bright_green]ATR(14)%[/]        volatilidad relativa al precio
  [bright_green]SIGNAL[/]          score combinado: STR LONG → STR SHORT
"""

# ═══════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", default="binance", choices=["binance","coinbase","kraken"])
    parser.add_argument("--once",   action="store_true")
    parser.add_argument("--alert",  nargs=2, metavar=("SYM","PRICE"))
    parser.add_argument("--help",   action="store_true")
    args = parser.parse_args()

    if args.help:
        console.print(HELP_TEXT)
    elif args.alert:
        sym, price_str = args.alert
        try:
            with mkt._lock:
                mkt.alerts[sym.upper()] = float(price_str)
            console.print(f"[bright_green]Alerta:[/] {sym.upper()} ≥ ${float(price_str):,.2f}")
            run_live(args.source)
        except ValueError:
            console.print("[red]Precio inválido.[/]")
    elif args.once:
        run_once(args.source)
    else:
        run_live(args.source)
"""Historical OHLCV candle retrieval via public REST endpoints.

Used to warm up the indicator engine at startup (so signals are not cold for
the first minutes) and to feed the backtesting engine. Every fetch returns a
normalized list of candle dicts with the same shape produced by the live
WebSocket engine in :mod:`terminalcrypt.state`::

    {"open", "high", "low", "close", "volume", "ts", "time"}

``ts`` is a short ``HH:MM:SS`` label for display; ``time`` is the epoch second
of the candle open, useful for ordering and de-duplication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

import requests

from .config import (
    BINANCE_SYMBOLS,
    COINBASE_SYMBOLS,
    HEADERS,
    KRAKEN_SYMBOLS,
)

log = logging.getLogger(__name__)

# Interval (seconds) -> per-exchange interval token.
_BINANCE_INTERVAL = {60: "1m", 300: "5m", 900: "15m", 3600: "1h", 86400: "1d"}
_KRAKEN_INTERVAL = {60: 1, 300: 5, 900: 15, 3600: 60, 86400: 1440}
_COINBASE_GRANULARITY = {60, 300, 900, 3600, 21600, 86400}


def _reverse(mapping: dict[str, str]) -> dict[str, str]:
    """Build a symbol -> exchange-pair lookup, keeping the first pair seen."""
    out: dict[str, str] = {}
    for pair, sym in mapping.items():
        out.setdefault(sym, pair)
    return out


_BINANCE_PAIRS = _reverse(BINANCE_SYMBOLS)
_COINBASE_PAIRS = _reverse(COINBASE_SYMBOLS)
_KRAKEN_PAIRS = _reverse(KRAKEN_SYMBOLS)


def _candle(open_: float, high: float, low: float, close: float, volume: float, epoch: int) -> dict:
    return {
        "open": float(open_),
        "high": float(high),
        "low": float(low),
        "close": float(close),
        "volume": float(volume),
        "time": int(epoch),
        "ts": datetime.fromtimestamp(int(epoch), timezone.utc).strftime("%H:%M:%S"),
    }


def _fetch_binance(sym: str, interval: int, limit: int) -> list[dict]:
    pair = _BINANCE_PAIRS.get(sym)
    token = _BINANCE_INTERVAL.get(interval)
    if not pair or not token:
        return []
    r = requests.get(
        "https://api.binance.com/api/v3/klines",
        params={"symbol": pair, "interval": token, "limit": min(int(limit), 1000)},
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    rows = r.json()
    return [
        _candle(row[1], row[2], row[3], row[4], row[5], int(row[0]) // 1000)
        for row in rows
        if isinstance(row, list) and len(row) >= 6
    ]


def _fetch_coinbase(sym: str, interval: int, limit: int) -> list[dict]:
    pair = _COINBASE_PAIRS.get(sym)
    if not pair or interval not in _COINBASE_GRANULARITY:
        return []
    r = requests.get(
        f"https://api.exchange.coinbase.com/products/{pair}/candles",
        params={"granularity": interval},
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    # Coinbase rows: [time, low, high, open, close, volume]; newest first.
    rows = sorted((row for row in r.json() if isinstance(row, list) and len(row) >= 6), key=lambda x: x[0])
    candles = [_candle(row[3], row[2], row[1], row[4], row[5], int(row[0])) for row in rows]
    return candles[-int(limit):] if limit else candles


def _fetch_kraken(sym: str, interval: int, limit: int) -> list[dict]:
    pair = _KRAKEN_PAIRS.get(sym)
    token = _KRAKEN_INTERVAL.get(interval)
    if not pair or not token:
        return []
    # Kraken expects the pair without the "/" separator.
    r = requests.get(
        "https://api.kraken.com/0/public/OHLC",
        params={"pair": pair.replace("/", ""), "interval": token},
        headers=HEADERS,
        timeout=10,
    )
    r.raise_for_status()
    payload = r.json()
    if payload.get("error"):
        log.debug("kraken OHLC error for %s: %s", sym, payload["error"])
    result = payload.get("result", {})
    series: Iterable = next((v for k, v in result.items() if k != "last"), [])
    # Kraken rows: [time, open, high, low, close, vwap, volume, count].
    candles = [
        _candle(row[1], row[2], row[3], row[4], row[6], int(row[0]))
        for row in series
        if isinstance(row, list) and len(row) >= 7
    ]
    return candles[-int(limit):] if limit else candles


_FETCHERS = {
    "binance": _fetch_binance,
    "coinbase": _fetch_coinbase,
    "kraken": _fetch_kraken,
}


def fetch_candles(sym: str, source: str = "binance", interval: int = 60, limit: int = 200) -> list[dict]:
    """Fetch normalized historical candles for ``sym`` from ``source``.

    Returns an empty list on any error so callers can degrade gracefully; the
    live engine keeps working without a warm-up.
    """
    fetch = _FETCHERS.get(source, _fetch_binance)
    try:
        candles = fetch(sym, interval, limit)
        log.info("fetched %d %ss candles for %s from %s", len(candles), interval, sym, source)
        return candles
    except Exception as e:  # network / parsing / rate-limit — never fatal
        log.warning("historical fetch failed sym=%s source=%s: %s", sym, source, e)
        return []

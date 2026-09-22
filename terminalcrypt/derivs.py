"""Derivatives market data: funding rates, open interest, liquidations.

Uses Binance USD-M Futures public endpoints. Funding rates and mark prices for
every perpetual come from a single ``premiumIndex`` call; open interest is
fetched per symbol for a small curated set to stay within rate limits.
Liquidation events arrive over a websocket (see
:class:`terminalcrypt.streams.BinanceLiquidationStream`) and are parsed by
:func:`parse_liquidation` here.

Everything is best-effort: network/parse failures return empty results so the
rest of the terminal keeps working.
"""

from __future__ import annotations

import logging

import requests

from .config import BINANCE_SYMBOLS, HEADERS

log = logging.getLogger(__name__)

FAPI = "https://fapi.binance.com"

# Futures pair -> internal symbol. Binance USD-M perps use the same USDT pairs.
_FUT_TO_SYM = dict(BINANCE_SYMBOLS)
_SYM_TO_FUT = {}
for _pair, _sym in BINANCE_SYMBOLS.items():
    _SYM_TO_FUT.setdefault(_sym, _pair)

# Symbols we pull open interest for (one REST call each).
OI_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX"]


def fetch_funding() -> dict[str, dict]:
    """Return ``{symbol: {funding_rate, mark_price}}`` for all perpetuals."""
    try:
        r = requests.get(f"{FAPI}/fapi/v1/premiumIndex", headers=HEADERS, timeout=10)
        r.raise_for_status()
        out: dict[str, dict] = {}
        for row in r.json():
            sym = _FUT_TO_SYM.get(row.get("symbol", ""))
            if not sym:
                continue
            try:
                out[sym] = {
                    "funding_rate": float(row.get("lastFundingRate", 0) or 0) * 100,  # percent
                    "mark_price": float(row.get("markPrice", 0) or 0),
                    "next_funding": int(row.get("nextFundingTime", 0) or 0),
                }
            except (TypeError, ValueError):
                continue
        return out
    except Exception as e:
        log.warning("funding fetch failed: %s", e)
        return {}


def fetch_open_interest(symbols: list[str] | None = None) -> dict[str, float]:
    """Return ``{symbol: open_interest_contracts}`` for the given symbols."""
    symbols = symbols or OI_SYMBOLS
    out: dict[str, float] = {}
    for sym in symbols:
        pair = _SYM_TO_FUT.get(sym)
        if not pair:
            continue
        try:
            r = requests.get(f"{FAPI}/fapi/v1/openInterest", params={"symbol": pair}, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue
            out[sym] = float(r.json().get("openInterest", 0) or 0)
        except Exception as e:
            log.debug("open interest fetch failed for %s: %s", sym, e)
            continue
    return out


def parse_liquidation(msg: dict) -> dict | None:
    """Parse a Binance ``forceOrder`` message into a normalized liquidation.

    ``side`` is the position that was liquidated: a forced SELL closes a long,
    a forced BUY closes a short.
    """
    order = msg.get("o", msg)
    pair = order.get("s", "")
    sym = _FUT_TO_SYM.get(pair)
    if not sym:
        return None
    try:
        price = float(order.get("ap") or order.get("p") or 0)
        qty = float(order.get("q", 0) or 0)
    except (TypeError, ValueError):
        return None
    if price <= 0 or qty <= 0:
        return None
    order_side = str(order.get("S", "")).upper()
    liquidated = "long" if order_side == "SELL" else "short"
    return {
        "symbol": sym,
        "side": liquidated,          # which side got liquidated
        "price": price,
        "qty": qty,
        "notional": price * qty,
    }

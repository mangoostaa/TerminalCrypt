"""Whale / large-trade detection over the trade tape.

Pure helpers that classify executed trades by notional value and summarize the
aggressive buy/sell pressure of the big players. They operate on the trade
dicts stored in :class:`~terminalcrypt.state.MarketState` (``price``, ``qty``,
``side``, ``ts``), so they are trivial to unit-test without any live feed.
"""

from __future__ import annotations

# A trade at or above this fraction of the whale threshold is "large";
# at or above the full threshold it is a "whale".
LARGE_FRACTION = 0.25


def classify(trade: dict, whale_usd: float) -> str:
    """Return ``"whale"``, ``"large"`` or ``"normal"`` for a single trade."""
    notional = float(trade.get("price", 0) or 0) * float(trade.get("qty", 0) or 0)
    if notional >= whale_usd:
        return "whale"
    if notional >= whale_usd * LARGE_FRACTION:
        return "large"
    return "normal"


def trade_notional(trade: dict) -> float:
    return float(trade.get("price", 0) or 0) * float(trade.get("qty", 0) or 0)


def whale_pressure(trades: list[dict], whale_usd: float) -> dict:
    """Summarize whale-sized flow: buy vs sell notional, count and bias.

    ``bias`` is in ``[-1, 1]`` (>0 = whales buying, <0 = whales selling).
    """
    buy_usd = 0.0
    sell_usd = 0.0
    whales = []
    for t in trades:
        notional = trade_notional(t)
        if notional < whale_usd:
            continue
        whales.append(t)
        if t.get("side") == "buy":
            buy_usd += notional
        else:
            sell_usd += notional
    total = buy_usd + sell_usd
    bias = (buy_usd - sell_usd) / total if total else 0.0
    return {
        "count": len(whales),
        "buy_usd": buy_usd,
        "sell_usd": sell_usd,
        "net_usd": buy_usd - sell_usd,
        "bias": round(bias, 3),
        "biggest": max(whales, key=trade_notional) if whales else None,
    }


def recent_whales(trades: list[dict], whale_usd: float, limit: int = 12) -> list[dict]:
    """Return the most recent whale trades, newest first, tagged with notional."""
    out = []
    for t in trades:
        notional = trade_notional(t)
        if notional >= whale_usd:
            out.append({**t, "notional": notional, "tier": classify(t, whale_usd)})
    return list(reversed(out))[:limit]

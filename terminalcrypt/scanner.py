from __future__ import annotations

from typing import Iterable

from rich.table import Table

from .analytics import analytics_cache
from .config import SYMBOLS_ORDERED
from .formatters import fmt_large, fmt_price

SCAN_MODES = ("movers", "volume", "signals")
SCAN_FIELDS = [
    "rank",
    "symbol",
    "price",
    "change_24h",
    "intraday",
    "volume_24h",
    "relative_volume",
    "score",
    "rsi",
    "ema_signal",
    "macd_histogram",
    "risk",
]


def _symbol_filter(symbols: Iterable[str] | None) -> set[str] | None:
    return {sym.upper() for sym in symbols} if symbols else None


def _base_row(snapshot: dict, sym: str) -> dict:
    indicators = analytics_cache.indicators(sym, snapshot)
    score = analytics_cache.symbol_score(sym, snapshot)
    return {
        "symbol": sym,
        "price": snapshot.get("prices", {}).get(sym, 0.0),
        "change_24h": snapshot.get("chg24h", {}).get(sym, 0.0),
        "intraday": analytics_cache.intraday_change(sym, snapshot),
        "volume_24h": snapshot.get("vol24", {}).get(sym, 0.0),
        "relative_volume": indicators.get("rvol", 0.0),
        "score": score.get("score", 0.0),
        "rsi": indicators.get("rsi", 0.0),
        "ema_signal": indicators.get("ema", {}).get("signal", ""),
        "macd_histogram": indicators.get("macd", {}).get("histogram", 0.0),
        "risk": score.get("risk", ""),
    }


def scan_snapshot(
    snapshot: dict,
    mode: str,
    limit: int = 10,
    symbols: Iterable[str] | None = None,
) -> list[dict]:
    if mode not in SCAN_MODES:
        raise ValueError(f"Unsupported scan mode: {mode}")

    selected = _symbol_filter(symbols)
    available = [
        sym
        for sym in SYMBOLS_ORDERED
        if snapshot.get("prices", {}).get(sym, 0) and (selected is None or sym in selected)
    ]
    rows = [_base_row(snapshot, sym) for sym in available]

    if mode == "movers":
        rows.sort(key=lambda row: abs(row["change_24h"]), reverse=True)
    elif mode == "volume":
        rows.sort(key=lambda row: (row["relative_volume"], row["volume_24h"]), reverse=True)
    else:
        rows.sort(key=lambda row: row["score"], reverse=True)

    return [{"rank": idx, **row} for idx, row in enumerate(rows[: max(1, limit)], start=1)]


def render_scan_table(rows: list[dict], mode: str) -> Table:
    title = {
        "movers": "Scanner: Movers 24h",
        "volume": "Scanner: Volumen",
        "signals": "Scanner: Senales",
    }[mode]
    table = Table(title=title, show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("SYM", style="bold bright_green")
    table.add_column("PRICE", justify="right")
    table.add_column("24H", justify="right")

    if mode == "movers":
        table.add_column("INTRA", justify="right")
        table.add_column("SCORE", justify="right")
    elif mode == "volume":
        table.add_column("VOL24", justify="right")
        table.add_column("RVOL", justify="right")
    else:
        table.add_column("SCORE", justify="right")
        table.add_column("RSI", justify="right")
        table.add_column("EMA", justify="center")
        table.add_column("RISK", justify="center")

    for row in rows:
        base = [
            str(row["rank"]),
            row["symbol"],
            fmt_price(row["price"]),
            f"{row['change_24h']:+.2f}%",
        ]
        if mode == "movers":
            extra = [f"{row['intraday']:+.2f}%", f"{row['score']:.1f}"]
        elif mode == "volume":
            extra = [fmt_large(row["volume_24h"]), f"{row['relative_volume']:.2f}x"]
        else:
            extra = [f"{row['score']:.1f}", f"{row['rsi']:.1f}", row["ema_signal"], row["risk"]]
        table.add_row(*base, *extra)
    return table

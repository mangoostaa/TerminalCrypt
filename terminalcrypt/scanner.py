from __future__ import annotations

from typing import Iterable

from rich.table import Table

from .analytics import analytics_cache
from .config import SYMBOLS_ORDERED
from .formatters import fmt_large, fmt_price

SCAN_MODES = ("movers", "volume", "signals", "setups")
SCAN_FIELDS = [
    "rank",
    "symbol",
    "side",
    "price",
    "entry",
    "stop_loss",
    "take_profit_1",
    "take_profit_2",
    "risk_reward_1",
    "risk_reward_2",
    "change_24h",
    "intraday",
    "volume_24h",
    "relative_volume",
    "score",
    "rsi",
    "ema_signal",
    "macd_histogram",
    "atr_pct",
    "spread",
    "risk",
    "reason",
]


def _symbol_filter(symbols: Iterable[str] | None) -> set[str] | None:
    return {sym.upper() for sym in symbols} if symbols else None


def _base_row(snapshot: dict, sym: str) -> dict:
    indicators = analytics_cache.indicators(sym, snapshot)
    score = analytics_cache.symbol_score(sym, snapshot)
    price = snapshot.get("prices", {}).get(sym, 0.0)
    atr_pct = score.get("atr", 0.0)
    spread = score.get("spread", snapshot.get("spread", {}).get(sym, 0.0))
    side = _setup_side(score.get("score", 0.0), indicators)
    setup = _setup_levels(price, atr_pct, spread, side)
    return {
        "symbol": sym,
        "side": side,
        "price": price,
        **setup,
        "change_24h": snapshot.get("chg24h", {}).get(sym, 0.0),
        "intraday": analytics_cache.intraday_change(sym, snapshot),
        "volume_24h": snapshot.get("vol24", {}).get(sym, 0.0),
        "relative_volume": indicators.get("rvol", 0.0),
        "score": score.get("score", 0.0),
        "rsi": indicators.get("rsi", 0.0),
        "ema_signal": indicators.get("ema", {}).get("signal", ""),
        "macd_histogram": indicators.get("macd", {}).get("histogram", 0.0),
        "atr_pct": atr_pct,
        "spread": spread,
        "risk": score.get("risk", ""),
        "reason": _setup_reason(score.get("score", 0.0), indicators, score),
    }


def _setup_side(score: float, indicators: dict) -> str:
    ema_signal = indicators.get("ema", {}).get("signal", "")
    macd_hist = indicators.get("macd", {}).get("histogram", 0.0)
    rsi = indicators.get("rsi", 50.0)
    if score <= 42 or (ema_signal == "BEAR" and macd_hist < 0 and rsi >= 45):
        return "SHORT"
    return "LONG"


def _setup_levels(price: float, atr_pct: float, spread: float, side: str) -> dict:
    if price <= 0:
        return {
            "entry": 0.0,
            "stop_loss": 0.0,
            "take_profit_1": 0.0,
            "take_profit_2": 0.0,
            "risk_reward_1": 1.5,
            "risk_reward_2": 2.5,
        }
    risk_pct = max((atr_pct or 0.0) * 1.4, (spread or 0.0) * 4.0, 0.8)
    risk_amount = price * risk_pct / 100
    if side == "SHORT":
        stop = price + risk_amount
        tp1 = price - risk_amount * 1.5
        tp2 = price - risk_amount * 2.5
    else:
        stop = price - risk_amount
        tp1 = price + risk_amount * 1.5
        tp2 = price + risk_amount * 2.5
    return {
        "entry": price,
        "stop_loss": round(stop, 10),
        "take_profit_1": round(tp1, 10),
        "take_profit_2": round(tp2, 10),
        "risk_reward_1": 1.5,
        "risk_reward_2": 2.5,
    }


def _setup_reason(score: float, indicators: dict, score_row: dict) -> str:
    parts = [f"score={score:.1f}", f"ema={indicators.get('ema', {}).get('signal', '')}"]
    parts.append(f"rsi={indicators.get('rsi', 0.0):.1f}")
    parts.append(f"rvol={indicators.get('rvol', 0.0):.2f}x")
    parts.append(f"risk={score_row.get('risk', '')}")
    return " ".join(parts)


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
    elif mode == "signals":
        rows.sort(key=lambda row: row["score"], reverse=True)
    else:
        rows.sort(key=lambda row: (abs(row["score"] - 50), row["relative_volume"]), reverse=True)

    return [{"rank": idx, **row} for idx, row in enumerate(rows[: max(1, limit)], start=1)]


def render_scan_table(rows: list[dict], mode: str) -> Table:
    title = {
        "movers": "Scanner: Movers 24h",
        "volume": "Scanner: Volumen",
        "signals": "Scanner: Senales",
        "setups": "Scanner: Trade Setups",
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
    elif mode == "signals":
        table.add_column("SCORE", justify="right")
        table.add_column("RSI", justify="right")
        table.add_column("EMA", justify="center")
        table.add_column("RISK", justify="center")
    else:
        table.add_column("SIDE", justify="center")
        table.add_column("STOP", justify="right")
        table.add_column("TP1", justify="right")
        table.add_column("TP2", justify="right")
        table.add_column("RR", justify="right")

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
        elif mode == "signals":
            extra = [f"{row['score']:.1f}", f"{row['rsi']:.1f}", row["ema_signal"], row["risk"]]
        else:
            extra = [
                row["side"],
                fmt_price(row["stop_loss"]),
                fmt_price(row["take_profit_1"]),
                fmt_price(row["take_profit_2"]),
                f"{row['risk_reward_1']:.1f}/{row['risk_reward_2']:.1f}",
            ]
        table.add_row(*base, *extra)
    return table

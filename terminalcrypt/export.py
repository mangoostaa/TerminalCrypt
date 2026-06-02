from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .analytics import analytics_cache
from .config import SYMBOLS_ORDERED
from .scanner import SCAN_FIELDS, scan_snapshot


EXPORT_FIELDS = [
    "symbol",
    "price",
    "change_24h",
    "high_24h",
    "low_24h",
    "volume_24h",
    "bid",
    "ask",
    "spread",
    "volume_delta",
    "latency_ms",
    "tick_count",
    "last_tick",
    "rsi",
    "ema_signal",
    "macd_histogram",
    "signal",
]


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    symbols = [part.strip().upper() for part in value.split(",") if part.strip()]
    return symbols or None


def snapshot_rows(snapshot: dict, symbols: Iterable[str] | None = None) -> list[dict]:
    prices = snapshot.get("prices", {})
    requested = list(symbols) if symbols else [sym for sym in SYMBOLS_ORDERED if sym in prices]
    rows = []
    for sym in requested:
        if sym not in prices:
            continue
        indicators = analytics_cache.indicators(sym, snapshot)
        macd = indicators.get("macd", {})
        ema = indicators.get("ema", {})
        signal = indicators.get("signal", {})
        rows.append(
            {
                "symbol": sym,
                "price": prices.get(sym),
                "change_24h": snapshot.get("chg24h", {}).get(sym, 0.0),
                "high_24h": snapshot.get("high24", {}).get(sym, 0.0),
                "low_24h": snapshot.get("low24", {}).get(sym, 0.0),
                "volume_24h": snapshot.get("vol24", {}).get(sym, 0.0),
                "bid": snapshot.get("bid", {}).get(sym, 0.0),
                "ask": snapshot.get("ask", {}).get(sym, 0.0),
                "spread": snapshot.get("spread", {}).get(sym, 0.0),
                "volume_delta": snapshot.get("volume_delta", {}).get(sym, 0.0),
                "latency_ms": snapshot.get("latency_ms", {}).get(sym, 0.0),
                "tick_count": snapshot.get("tick_count", {}).get(sym, 0),
                "last_tick": snapshot.get("last_tick", {}).get(sym, ""),
                "rsi": indicators.get("rsi"),
                "ema_signal": ema.get("signal", ""),
                "macd_histogram": macd.get("histogram", 0.0),
                "signal": signal.get("label", ""),
            }
        )
    return rows


def _render_rows(
    snapshot: dict,
    output_format: str,
    rows: list[dict],
    fields: list[str],
    scan_mode: str | None = None,
) -> str:
    if output_format == "json":
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": snapshot.get("ws_source", ""),
            "status": snapshot.get("ws_status", ""),
            "ticks": snapshot.get("ws_ticks", 0),
            "rows": rows,
        }
        if scan_mode:
            payload["scan"] = scan_mode
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if output_format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue().rstrip("\n")
    raise ValueError(f"Unsupported export format: {output_format}")


def render_snapshot(snapshot: dict, output_format: str, symbols: Iterable[str] | None = None) -> str:
    return _render_rows(snapshot, output_format, snapshot_rows(snapshot, symbols), EXPORT_FIELDS)


def render_scan(
    snapshot: dict,
    output_format: str,
    mode: str,
    limit: int = 10,
    symbols: Iterable[str] | None = None,
) -> str:
    rows = scan_snapshot(snapshot, mode, limit, symbols)
    return _render_rows(snapshot, output_format, rows, SCAN_FIELDS, scan_mode=mode)


def write_snapshot(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content + "\n", encoding="utf-8")

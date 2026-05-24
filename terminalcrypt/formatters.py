from __future__ import annotations

from datetime import datetime, timezone
from rich.text import Text


def fmt_price(p: float) -> str:
    if p <= 0:
        return "    ─     "
    if p >= 1_000:
        return f"${p:>12,.2f}"
    if p >= 1:
        return f"${p:>12.4f}"
    return f"${p:>12.6f}"


def fmt_large(n: float) -> str:
    if n <= 0:
        return "─"
    if n >= 1e12:
        return f"${n/1e12:.2f}T"
    if n >= 1e9:
        return f"${n/1e9:.2f}B"
    if n >= 1e6:
        return f"${n/1e6:.2f}M"
    return f"${n:,.0f}"


def pct_color(v: float) -> str:
    if v >= 5:
        return "bright_green"
    if v >= 2:
        return "green"
    if v >= 0:
        return "dark_green"
    if v >= -2:
        return "yellow"
    if v >= -5:
        return "red"
    return "bright_red"


def pct_text(v: float) -> Text:
    if v == 0:
        return Text("  ──   ", style="dim")
    arrow = "▲" if v >= 0 else "▼"
    return Text(f"{arrow}{abs(v):6.2f}%", style=pct_color(v))


def fg_color(v: int) -> str:
    if v < 25:
        return "bright_red"
    if v < 45:
        return "dark_orange3"
    if v < 55:
        return "yellow"
    if v < 75:
        return "green"
    return "bright_green"


def fg_label(v: int) -> str:
    if v < 25:
        return "EXTREME FEAR"
    if v < 45:
        return "FEAR"
    if v < 55:
        return "NEUTRAL"
    if v < 75:
        return "GREED"
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
    cur = s["prices"].get(sym, 0)
    prev = s["prev"].get(sym, cur)
    if cur > prev:
        return "bold bright_green"
    if cur < prev:
        return "bold bright_red"
    return "bold bright_white"

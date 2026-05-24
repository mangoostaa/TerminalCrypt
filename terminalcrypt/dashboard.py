from __future__ import annotations

import time
from datetime import datetime, timezone
from rich import box
from rich.layout import Layout
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .config import COINBASE_SYMBOLS, SYMBOL_CATEGORIES, SYMBOL_NAME, SYMBOLS_ORDERED
from .formatters import (
    fmt_price,
    pct_text,
    price_flash_color,
    sparkline,
)
from .indicators import (
    calculate_atr,
    calculate_bollinger,
    calculate_ema_cross,
    calculate_macd,
    calculate_rsi,
    calculate_signal,
    relative_volume,
)

_ticker_offset = 0
_ticker_last = 0.0
_prices_page = 0
_prices_last_p = 0.0


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _coinbase_score(sym: str, s: dict) -> dict:
    price = s["prices"].get(sym, 0)
    hist = list(s.get("history", {}).get(sym, []))
    vol_hist = list(s.get("volume_history", {}).get(sym, []))
    highs = list(s.get("high_history", {}).get(sym, []))
    lows = list(s.get("low_history", {}).get(sym, []))
    chg = s["chg24h"].get(sym, 0)
    spread = s["spread"].get(sym, 0)
    vol24 = s["vol24"].get(sym, 0)

    rsi = calculate_rsi(hist)
    ema = calculate_ema_cross(hist)
    macd = calculate_macd(hist)
    bb = calculate_bollinger(hist)
    atr = calculate_atr(highs, lows, hist)
    rvol = relative_volume(vol_hist, vol24)

    momentum = _clamp(chg / 8, -1, 1) * 22
    trend = 0
    if ema["signal"] == "BULL":
        trend += 18
    elif ema["signal"] == "BEAR":
        trend -= 18
    if ema["cross"]:
        trend += 6 if ema["signal"] == "BULL" else -6

    macd_pct = (macd["histogram"] / price * 100) if price else 0
    macd_score = _clamp(macd_pct * 22, -14, 14)
    if macd["direction"] == "UP":
        macd_score += 4
    elif macd["direction"] == "DOWN":
        macd_score -= 4

    if 45 <= rsi <= 62:
        rsi_score = 14
    elif 35 <= rsi < 45 or 62 < rsi <= 70:
        rsi_score = 6
    elif rsi < 30:
        rsi_score = -5
    else:
        rsi_score = -12

    bb_zone = bb["zone"]
    bb_score = {"LOW": 8, "MID": 5, "BELOW": 4, "HIGH": -5, "ABOVE": -10}.get(bb_zone, 0)
    liquidity = _clamp((rvol - 1) * 7, -4, 12)
    spread_penalty = _clamp(spread * 35, 0, 14) if spread else 0
    atr_penalty = _clamp(max(atr - 4, 0) * 3, 0, 12)
    data_bonus = _clamp(len(hist) / 80, 0, 1) * 8

    raw = 50 + momentum + trend + macd_score + rsi_score + bb_score + liquidity + data_bonus
    score = round(_clamp(raw - spread_penalty - atr_penalty, 0, 100), 1)
    risk = "ALTO" if atr >= 4 or spread >= 0.35 else "MEDIO" if atr >= 2 or spread >= 0.15 else "BAJO"

    return {
        "sym": sym,
        "price": price,
        "score": score,
        "chg": chg,
        "rsi": rsi,
        "ema": ema,
        "macd": macd,
        "bb": bb,
        "atr": atr,
        "rvol": rvol,
        "spread": spread,
        "risk": risk,
        "history": hist,
    }


def _coinbase_rankings(s: dict) -> list[dict]:
    symbols = sorted(set(COINBASE_SYMBOLS.values()))
    rows = [_coinbase_score(sym, s) for sym in symbols if s["prices"].get(sym, 0)]
    return sorted(rows, key=lambda row: row["score"], reverse=True)


def panel_header(s: dict) -> Panel:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d  %H:%M:%S.%f")[:-3] + " UTC"
    g = Table.grid(expand=True)
    g.add_column()
    g.add_column(justify="center")
    g.add_column(justify="right")
    g.add_row(
        Text("◈ AZ TERMINAL v3.2", style="bold bright_green"),
        Text(f"[{s['ws_source']}]  {s['ws_status']}  ✦ {s['ws_ticks']:,} ticks", style="dim green"),
        Text(ts, style="dim green"),
    )
    return Panel(g, border_style="bright_green", padding=(0, 1))


def panel_ticker(s: dict) -> Panel:
    global _ticker_offset, _ticker_last
    now = time.monotonic()
    active = [sym for sym in SYMBOLS_ORDERED if s["prices"].get(sym, 0)]
    if active:
        window = 18
        if now - _ticker_last > 4.0:
            _ticker_offset = (_ticker_offset + window) % len(active)
            _ticker_last = now
        visible = (active[_ticker_offset:] + active[:_ticker_offset])[:window]
    else:
        visible = []

    parts = []
    for sym in visible:
        p = s["prices"].get(sym, 0)
        chg = s["chg24h"].get(sym, 0)
        if not p:
            continue
        col = "bright_green" if chg >= 0 else "bright_red"
        ar = "▲" if chg >= 0 else "▼"
        parts.append(
            f"[bold bright_green]{sym}[/] [white]${p:,.4g}[/] "
            f"[{col}]{ar}{abs(chg):.2f}%[/]  [dim dark_green]│[/]  "
        )
    total = len(active)
    suffix = f"  [dim green]({total} pares activos)[/]" if total else ""
    txt = Text.from_markup("".join(parts) + suffix) if parts else Text("Conectando WS...", style="dim green")
    return Panel(txt, border_style="dark_green", padding=(0, 1))


def panel_prices(s: dict) -> Panel:
    global _prices_page, _prices_last_p
    now = time.monotonic()
    cat_names = list(SYMBOL_CATEGORIES.keys())
    if now - _prices_last_p > 8.0:
        _prices_page = (_prices_page + 1) % len(cat_names)
        _prices_last_p = now

    current_cat = cat_names[_prices_page]
    cat_symbols = SYMBOL_CATEGORIES[current_cat]
    page_info = f"[dim]cat {_prices_page+1}/{len(cat_names)} — {current_cat}[/]"

    tbl = Table(
        box=box.SIMPLE_HEAVY,
        border_style="dark_green",
        header_style="bold bright_green",
        show_lines=False,
        expand=True,
        padding=(0, 1),
    )
    tbl.add_column("SYM", style="bold bright_green", min_width=6)
    tbl.add_column("NOMBRE", style="dim green", min_width=14)
    tbl.add_column("LAST", justify="right", min_width=14)
    tbl.add_column("24H%", justify="right", min_width=9)
    tbl.add_column("RSI", justify="right", min_width=5)
    tbl.add_column("EMA", justify="center", min_width=7)
    tbl.add_column("MACD", justify="right", min_width=9)
    tbl.add_column("BB", justify="center", min_width=7)
    tbl.add_column("ATR%", justify="right", min_width=6)
    tbl.add_column("SIGNAL", justify="center", min_width=10)
    tbl.add_column("RVOL", justify="right", min_width=6)
    tbl.add_column("SPREAD", justify="right", min_width=7)
    tbl.add_column("SPARK", min_width=14)

    active_total = sum(1 for sym in SYMBOLS_ORDERED if s["prices"].get(sym, 0))
    for sym in cat_symbols:
        price = s["prices"].get(sym, 0)
        if not price:
            tbl.add_row(
                Text(sym, style="dim"),
                Text(SYMBOL_NAME.get(sym, ""), style="dim"),
                Text("─ esperando", style="dim"),
                *["─"] * 10,
            )
            continue

        chg = s["chg24h"].get(sym, 0)
        spread = s["spread"].get(sym, 0)
        hist = list(s.get("history", {}).get(sym, []))
        vol_hist = list(s.get("volume_history", {}).get(sym, []))
        highs = list(s.get("high_history", {}).get(sym, []))
        lows = list(s.get("low_history", {}).get(sym, []))
        vol24 = s["vol24"].get(sym, 0)

        rsi = calculate_rsi(hist)
        ema_data = calculate_ema_cross(hist)
        macd_data = calculate_macd(hist)
        bb_data = calculate_bollinger(hist)
        atr_pct = calculate_atr(highs, lows, hist)
        rel_vol = relative_volume(vol_hist, vol24)
        sig_data = calculate_signal(rsi, ema_data, macd_data, bb_data)

        price_col = price_flash_color(sym, s)
        rsi_color = "bright_red" if rsi > 70 else "bright_green" if rsi < 30 else "yellow"
        vol_color = "bright_green" if rel_vol > 2.5 else "green" if rel_vol > 1.5 else "dim white"

        ema_col = "bright_green" if ema_data["signal"] == "BULL" else "bright_red"
        ema_txt = "▲ BULL" if ema_data["signal"] == "BULL" else "▼ BEAR"
        if ema_data["cross"]:
            ema_txt += "✦"

        hist_val = macd_data["histogram"]
        macd_col = "bright_green" if hist_val > 0 else "bright_red"
        macd_arrow = "▲" if macd_data["direction"] == "UP" else "▼"
        macd_str = f"{macd_arrow}{hist_val:+.3f}" if abs(hist_val) >= 0.01 else f"{macd_arrow}{hist_val*1000:+.2f}‰"

        bb_zone = bb_data["zone"]
        bb_colors = {"ABOVE": "bright_red", "HIGH": "red", "MID": "yellow", "LOW": "green", "BELOW": "bright_green"}
        bb_icons = {"ABOVE": "↑↑ OB", "HIGH": "↑  HI", "MID": "── MID", "LOW": "↓  LO", "BELOW": "↓↓ OS"}
        atr_col = "bright_red" if atr_pct > 3 else "yellow" if atr_pct > 1.5 else "dim green"

        tbl.add_row(
            sym,
            SYMBOL_NAME.get(sym, ""),
            Text(fmt_price(price), style=price_col),
            pct_text(chg),
            Text(f"{rsi}", style=rsi_color),
            Text(ema_txt, style=ema_col),
            Text(macd_str, style=macd_col),
            Text(bb_icons.get(bb_zone, bb_zone), style=bb_colors.get(bb_zone, "white")),
            Text(f"{atr_pct:.2f}%" if atr_pct else "─", style=atr_col),
            Text(sig_data["signal"], style=sig_data["color"]),
            Text(f"{rel_vol:.1f}x", style=vol_color),
            Text(f"{spread:.3f}%" if spread else "─", style="dim white"),
            sparkline(hist, 14),
        )

    return Panel(
        tbl,
        title=(
            f"[bold bright_green]◆ MARKETS — {current_cat}[/]  {page_info}  "
            f"[dim]total activos: {active_total}/{len(SYMBOLS_ORDERED)}  auto-rotación 8s  src:{s['ws_source']}[/]"
        ),
        border_style="green",
    )


def panel_coinbase_top5(s: dict) -> Panel:
    rankings = _coinbase_rankings(s)
    tbl = Table(
        box=box.SIMPLE_HEAVY,
        border_style="dark_green",
        header_style="bold bright_green",
        show_lines=False,
        expand=True,
        padding=(0, 1),
    )
    tbl.add_column("#", justify="right", min_width=3)
    tbl.add_column("SYM", style="bold bright_green", min_width=6)
    tbl.add_column("NOMBRE", style="dim green", min_width=14)
    tbl.add_column("SCORE", justify="right", min_width=8)
    tbl.add_column("LAST", justify="right", min_width=14)
    tbl.add_column("24H%", justify="right", min_width=9)
    tbl.add_column("RSI", justify="right", min_width=5)
    tbl.add_column("EMA", justify="center", min_width=7)
    tbl.add_column("MACD", justify="right", min_width=9)
    tbl.add_column("BB", justify="center", min_width=7)
    tbl.add_column("RVOL", justify="right", min_width=6)
    tbl.add_column("ATR%", justify="right", min_width=7)
    tbl.add_column("SPREAD", justify="right", min_width=7)
    tbl.add_column("RIESGO", justify="center", min_width=7)
    tbl.add_column("SPARK", min_width=14)

    if not rankings:
        tbl.add_row(
            "─",
            "─",
            Text("Esperando ticks de símbolos Coinbase", style="dim"),
            *["─"] * 12,
        )
    for idx, row in enumerate(rankings[:5], start=1):
        score = row["score"]
        score_color = "bold bright_green" if score >= 75 else "green" if score >= 62 else "yellow"
        ema = row["ema"]
        if ema["signal"] == "BULL":
            ema_txt = "▲ BULL"
            ema_col = "bright_green"
        elif ema["signal"] == "BEAR":
            ema_txt = "▼ BEAR"
            ema_col = "bright_red"
        else:
            ema_txt = "─ NEU"
            ema_col = "yellow"
        if ema["cross"]:
            ema_txt += "✦"

        macd = row["macd"]
        macd_col = "bright_green" if macd["histogram"] > 0 else "bright_red"
        macd_arrow = "▲" if macd["direction"] == "UP" else "▼"
        macd_str = f"{macd_arrow}{macd['histogram']:+.3f}" if abs(macd["histogram"]) >= 0.01 else f"{macd_arrow}{macd['histogram']*1000:+.2f}‰"

        risk_col = "bright_red" if row["risk"] == "ALTO" else "yellow" if row["risk"] == "MEDIO" else "green"
        bb_zone = row["bb"]["zone"]
        bb_colors = {"ABOVE": "bright_red", "HIGH": "red", "MID": "yellow", "LOW": "green", "BELOW": "bright_green"}
        bb_icons = {"ABOVE": "↑↑ OB", "HIGH": "↑  HI", "MID": "── MID", "LOW": "↓  LO", "BELOW": "↓↓ OS"}

        tbl.add_row(
            str(idx),
            row["sym"],
            SYMBOL_NAME.get(row["sym"], ""),
            Text(f"{score:5.1f}", style=score_color),
            Text(fmt_price(row["price"]), style=price_flash_color(row["sym"], s)),
            pct_text(row["chg"]),
            Text(f"{row['rsi']}", style="bright_red" if row["rsi"] > 70 else "bright_green" if row["rsi"] < 30 else "yellow"),
            Text(ema_txt, style=ema_col),
            Text(macd_str, style=macd_col),
            Text(bb_icons.get(bb_zone, bb_zone), style=bb_colors.get(bb_zone, "white")),
            Text(f"{row['rvol']:.1f}x", style="bright_green" if row["rvol"] > 2.5 else "green" if row["rvol"] > 1.5 else "dim white"),
            Text(f"{row['atr']:.2f}%" if row["atr"] else "─", style="bright_red" if row["atr"] > 3 else "yellow" if row["atr"] > 1.5 else "dim green"),
            Text(f"{row['spread']:.3f}%" if row["spread"] else "─", style="dim white"),
            Text(row["risk"], style=risk_col),
            sparkline(row["history"], 14),
        )

    return Panel(
        tbl,
        title=(
            "[bold bright_green]◆ TOP 5 CUANTITATIVO — UNIVERSO COINBASE[/]  "
            "[dim]score: momentum+EMA+MACD+RSI+BB+RVOL-spread-volatilidad  TAB/I alterna[/]"
        ),
        border_style="green",
    )


def panel_quant_legend() -> Panel:
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(style="bold bright_green", min_width=10)
    tbl.add_column(style="dim green")
    tbl.add_row("SCORE", "0-100; ranking cuantitativo, no garantía")
    tbl.add_row("Momentum", "cambio 24h normalizado")
    tbl.add_row("Tendencia", "EMA 9/21 + cruce reciente")
    tbl.add_row("MACD", "histograma relativo al precio")
    tbl.add_row("RSI/BB", "premia fuerza no sobrecomprada")
    tbl.add_row("Liquidez", "RVOL alto y spread bajo")
    tbl.add_row("Riesgo", "ATR y spread penalizan")
    return Panel(tbl, title="[bold bright_green]MODELO[/]", border_style="dark_green", padding=(0, 1))


def panel_indicators_legend() -> Panel:
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(style="bold bright_green", min_width=9)
    tbl.add_column(style="dim green")
    tbl.add_row("RSI(14)", "< 30 sobreventa  > 70 sobrecompra")
    tbl.add_row("EMA 9/21", "▲ BULL cruce alcista  ✦ cruce reciente")
    tbl.add_row("MACD", "▲/▼ hist. sube/baja  ‰ = ×1000")
    tbl.add_row("BB(20,2σ)", "↑↑ OB sobrecompra  ↓↓ OS sobreventa")
    tbl.add_row("ATR%", "volatilidad  > 3% alta  < 1.5% baja")
    tbl.add_row("SIGNAL", "RSI+EMA+MACD+BB → STR LONG/SHORT")
    tbl.add_row("RVOL", "volumen relativo  > 2.5x inusual")
    return Panel(tbl, title="[bold bright_green]LEYENDA[/]", border_style="dark_green", padding=(0, 1))


def panel_fg(s: dict) -> Panel:
    items = s["fg_data"]
    if not items:
        return Panel("[dim green]Cargando Fear & Greed...[/]", title="FEAR & GREED", border_style="green")
    vals = [int(d["value"]) for d in items]
    cur = vals[0]
    col = "bright_green" if cur >= 75 else "green" if cur >= 55 else "yellow" if cur >= 45 else "dark_orange3" if cur >= 25 else "bright_red"
    lbl = "EXTREME GREED" if cur >= 75 else "GREED" if cur >= 55 else "NEUTRAL" if cur >= 45 else "FEAR" if cur >= 25 else "EXTREME FEAR"
    bar_n = int(cur / 100 * 22)
    bar = "█" * bar_n + "░" * (22 - bar_n)
    g = Table.grid(padding=(0, 0), expand=True)
    g.add_column(justify="center")
    g.add_row(Text(str(cur), style=f"bold {col}", justify="center"))
    g.add_row(Text(lbl, style=f"bold {col}", justify="center"))
    g.add_row(Text(bar, style=col, justify="center"))
    st = Table.grid(expand=True)
    st.add_column(style="dim green")
    st.add_column(justify="right")
    for label, idx in [("AYER", 1), ("SEMANA", 7), ("MES", 30)]:
        if idx < len(vals):
            v = vals[idx]
            v_lbl = "EXTREME GREED" if v >= 75 else "GREED" if v >= 55 else "NEUTRAL" if v >= 45 else "FEAR" if v >= 25 else "EXTREME FEAR"
            v_col = "bright_green" if v >= 75 else "green" if v >= 55 else "yellow" if v >= 45 else "dark_orange3" if v >= 25 else "bright_red"
            st.add_row(label, Text(f"{v}  {v_lbl[:4]}", style=v_col))
    g.add_row(sparkline(list(reversed(vals[:30])), 22))
    g.add_row(st)
    return Panel(g, title="[bold bright_green]FEAR & GREED 30d[/]", border_style="green", padding=(0, 1))


def panel_global(s: dict) -> Panel:
    g = s["global"]
    if not g:
        return Panel("[dim green]Cargando...[/]", title="GLOBAL", border_style="green")
    mc = g.get("total_market_cap", {}).get("usd", 0)
    vol = g.get("total_volume", {}).get("usd", 0)
    chg = g.get("market_cap_change_percentage_24h_usd", 0)
    dom = g.get("market_cap_percentage", {})
    coins = g.get("active_cryptocurrencies", 0)
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(style="dim green")
    tbl.add_column(justify="right")
    tbl.add_row("MKT CAP", Text(fmt_price(mc), style="bold bright_white"))
    tbl.add_row("24H CHG", pct_text(chg))
    tbl.add_row("VOLUMEN 24H", Text(fmt_price(vol), style="bright_white"))
    tbl.add_row("MONEDAS", Text(f"{coins:,}", style="bright_white"))
    tbl.add_row(Rule(style="dark_green"), "")
    top = sorted(dom.items(), key=lambda x: x[1], reverse=True)[:6]
    for sym, pct in top:
        bar = "█" * int(pct / 4) + "░" * max(0, 18 - int(pct / 4))
        tbl.add_row(Text(sym.upper(), style="green"), Text(f"{pct:5.1f}% {bar[:12]}", style="dark_green"))
    tbl.add_row(Rule(style="dark_green"), "")
    tbl.add_row("REST upd", Text(s["global_upd"], style="dim green"))
    return Panel(tbl, title="[bold bright_green]GLOBAL[/]", border_style="green", padding=(0, 1))


def panel_ws_stats(s: dict) -> Panel:
    tbl = Table.grid(padding=(0, 1), expand=True)
    tbl.add_column(style="dim green")
    tbl.add_column(justify="right")
    tbl.add_row("[bold]WS STATUS[/bold]", "")
    tbl.add_row("FUENTE", Text(s["ws_source"], style="bold bright_green"))
    tbl.add_row("ESTADO", Text(s["ws_status"], style="green" if "✓" in s["ws_status"] else "yellow"))
    tbl.add_row("DESDE", Text(s["ws_since"], style="dim green"))
    tbl.add_row("TICKS", Text(f"{s['ws_ticks']:,}", style="bright_white"))
    tbl.add_row("RECONEX", Text(str(s["ws_reconnects"]), style="yellow" if s["ws_reconnects"] else "dim green"))
    tbl.add_row(Rule(style="dark_green"), "")
    tbl.add_row("[bold]LAST TICK[/bold]", "")
    for sym in ["BTC", "ETH", "SOL", "BNB"]:
        lt = s["last_tick"].get(sym, "─")
        lat = s["latency_ms"].get(sym, 0)
        lat_str = f"{lat:.1f}ms" if lat else "─"
        tbl.add_row(f"  {sym}", Text(f"{lt}  {lat_str}", style="dim green"))
    if s["alerts"]:
        tbl.add_row(Rule(style="dark_green"), "")
        tbl.add_row("[bold]ALERTAS[/bold]", "")
        for sym, target in s["alerts"].items():
            tbl.add_row(f"  {sym}", Text(f"≥ {fmt_price(target).strip()}", style="yellow"))
    if s["triggered"]:
        tbl.add_row(Rule(style="dark_green"), "")
        for ts, msg in s["triggered"][-3:]:
            tbl.add_row(f"  {ts}", Text(msg[:28], style="bold yellow"))
    if s["errors"]:
        tbl.add_row(Rule(style="dark_green"), "")
        for k, v in s["errors"].items():
            tbl.add_row(Text(f"  ✗ {k}", style="red"), Text(v[:20], style="dim red"))
    return Panel(tbl, title="[bold bright_green]WS STATS & ALERTAS[/]", border_style="green", padding=(0, 1))


def panel_news(s: dict) -> Panel:
    news = s["news"]
    if not news:
        err = s["errors"].get("news", "Cargando noticias...")
        return Panel(Text(err, style="dim green"), title="[bold bright_green]◆ NOTICIAS CRYPTO[/]", border_style="green")
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
    return Panel(
        tbl,
        title=f"[bold bright_green]◆ NOTICIAS CRYPTO [dim]— {s['news_upd']}[/][/]",
        border_style="green",
        padding=(0, 1),
    )


def panel_footer(s: dict, view: str = "markets") -> Panel:
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3] + " UTC"
    view_name = "TOP 5 COINBASE" if view == "top5" else "MARKETS"
    txt = (
        f"[dim green]● WS LIVE — {s['ws_source']}[/]  "
        f"[dim]{s['ws_ticks']:,} ticks  │  ~{len(SYMBOLS_ORDERED)} pares  │  "
        f"vista: {view_name}  │  TAB/I alternar  M markets  │  "
        f"Ctrl+C salir[/]  [dim green]{ts}[/]"
    )
    return Panel(Text.from_markup(txt), border_style="dark_green", padding=(0, 1))


def build_dashboard(s: dict, view: str = "markets") -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="ticker", size=3),
        Layout(name="body", ratio=1),
        Layout(name="news", size=12),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(Layout(name="prices", ratio=5), Layout(name="sidebar", ratio=1))
    layout["sidebar"].split_column(
        Layout(name="legend", ratio=4),
        Layout(name="fg", ratio=5),
        Layout(name="global", ratio=4),
        Layout(name="ws", ratio=4),
    )
    layout["header"].update(panel_header(s))
    layout["ticker"].update(panel_ticker(s))
    if view == "top5":
        layout["prices"].update(panel_coinbase_top5(s))
        layout["legend"].update(panel_quant_legend())
    else:
        layout["prices"].update(panel_prices(s))
        layout["legend"].update(panel_indicators_legend())
    layout["fg"].update(panel_fg(s))
    layout["global"].update(panel_global(s))
    layout["ws"].update(panel_ws_stats(s))
    layout["news"].update(panel_news(s))
    layout["footer"].update(panel_footer(s, view))
    return layout

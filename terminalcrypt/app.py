from __future__ import annotations

import logging
import signal
import sys
import threading
import time
from typing import Optional

from rich.console import Console
from rich.live import Live

from .config import HELP_TEXT, SYMBOLS_ORDERED
from .dashboard import build_dashboard
from .export import render_scan, render_snapshot, write_snapshot
from .history import fetch_candles
from .notifications import start_surge_notifications
from .portfolio import Portfolio
from .rest import start_rest
from .scanner import render_scan_table, scan_snapshot
from .settings import AppSettings
from .state import MarketState
from .storage import SQLiteTickStore
from .streams import BinanceFocusStream, BinanceStream, CoinbaseStream, KrakenStream

log = logging.getLogger(__name__)

# Symbols warmed up with historical candles at startup (plus selected + portfolio).
WARMUP_DEFAULTS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX"]


STARTUP_BANNER = r"""
      ___      ______   _______  _______  ______   __   __  ___   __    _  _______  ___
     /   \    |____  | |       ||       ||    _ | |  |_|  ||   | |  |  | ||   _   ||   |
    /  ^  \       / /  |_     _||    ___||   | || |       ||   | |   |_| ||  |_|  ||   |
   /  /_\  \     / /     |   |  |   |___ |   |_||_|       ||   | |       ||       ||   |
  /  _____  \   / /      |   |  |    ___||    __  ||     | |   | |  _    ||       ||   |
 /__/     \__\ / /       |   |  |   |___ |   |  | ||   _   ||   | | | |   ||   _   ||   |
             /_/         |___|  |_______||___|  |_||__| |__||___| |_|  |__||__| |__||___|
"""

BOOT_SEQUENCE = (
    "[ OK ] loading market intelligence core",
    "[ OK ] websocket uplink armed",
    "[ OK ] volatility matrix online",
    "[ OK ] scanner modules: movers volume signals setups",
    "[ OK ] ACCESS GRANTED :: AZ TERMINAL",
)


class CryptexApp:
    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or AppSettings()
        self._tick_store = None
        if self.settings.sqlite_enabled:
            self._tick_store = SQLiteTickStore(self.settings.sqlite_path, self.settings.sqlite_batch_size)
            self._tick_store.start()
        self.state = MarketState(tick_recorder=self._tick_store)
        self._stream = None
        self._focus = None
        self._notifier = None
        self.console = Console()
        self.view = self.settings.initial_view
        self.selected_symbol = self.settings.selected_symbol
        self.portfolio: Portfolio | None = None
        if self.settings.portfolio_file:
            self.load_portfolio(self.settings.portfolio_file)

    def load_portfolio(self, path: str) -> None:
        try:
            self.portfolio = Portfolio.load(path)
            log.info("loaded portfolio %s with %d holdings", path, len(self.portfolio.holdings))
        except Exception as e:
            log.warning("could not load portfolio %s: %s", path, e)
            self.console.print(f"[red]No se pudo cargar portfolio {path}: {e}[/]")

    def _print_startup_banner(self, source: str, mode: str = "LIVE") -> None:
        self.console.print(f"[bold bright_green]{STARTUP_BANNER}[/]", highlight=False)
        self.console.print(
            f"[bold green]:: AZ TERMINAL v3.2 :: {mode} :: SOURCE={source.upper()} ::[/]",
            highlight=False,
        )
        for line in BOOT_SEQUENCE:
            self.console.print(f"[dim green]{line}[/]", highlight=False)
        self.console.print()

    def _read_key(self) -> Optional[str]:
        if sys.platform.startswith("win"):
            try:
                import msvcrt

                if msvcrt.kbhit():
                    return msvcrt.getwch()
            except Exception:
                return None
        else:
            try:
                import select

                if select.select([sys.stdin], [], [], 0)[0]:
                    return sys.stdin.read(1)
            except Exception:
                return None
        return None

    def _handle_key(self, key: Optional[str]) -> None:
        if not key:
            return
        if key in ("\t", "i", "I"):
            self.view = "top5" if self.view == "markets" else "markets"
        elif key in ("m", "M"):
            self.view = "markets"
        elif key in ("d", "D"):
            self.view = "detail"
            self._follow_selected()
        elif key in ("w", "W"):
            self.view = "portfolio"
        elif key in ("n", "N"):
            self._move_selected(1)
        elif key in ("p", "P"):
            self._move_selected(-1)

    def _move_selected(self, step: int) -> None:
        with self.state._lock:
            active = set(self.state.prices)
        symbols = [sym for sym in SYMBOLS_ORDERED if sym in active] or SYMBOLS_ORDERED
        try:
            idx = symbols.index(self.selected_symbol)
        except ValueError:
            idx = 0
        self.selected_symbol = symbols[(idx + step) % len(symbols)]
        self._follow_selected()

    def _follow_selected(self) -> None:
        """Point the focused depth/trade stream at the selected symbol."""
        if self._focus:
            self._focus.set_symbol(self.selected_symbol)

    def start_streams(self, source: str) -> None:
        if source == "coinbase":
            self._stream = CoinbaseStream(self.state)
        elif source == "kraken":
            self._stream = KrakenStream(self.state)
        else:
            self._stream = BinanceStream(self.state)
        self._stream.start()
        if self.settings.depth_enabled:
            self._focus = BinanceFocusStream(self.state, self.selected_symbol)
            self._focus.start()

    def _warmup(self, source: str) -> None:
        """Seed indicator history with recent candles so signals aren't cold."""
        if not self.settings.warmup_enabled:
            return
        symbols = list(dict.fromkeys(
            [self.selected_symbol] + WARMUP_DEFAULTS + (self.portfolio.symbols if self.portfolio else [])
        ))

        def _run():
            for sym in symbols:
                candles = fetch_candles(sym, source=source, interval=60, limit=120)
                if candles:
                    self.state.seed_candles(sym, candles)

        threading.Thread(target=_run, name="warmup", daemon=True).start()

    def portfolio_eval(self) -> dict | None:
        if not self.portfolio:
            return None
        with self.state._lock:
            prices = dict(self.state.prices)
        return self.portfolio.evaluate(prices)

    def _start_background_services(self) -> None:
        if self.settings.rest_enabled:
            start_rest(
                self.state,
                fg_interval=self.settings.fg_interval,
                global_interval=self.settings.global_interval,
                news_interval=self.settings.news_interval,
            )
        if self.settings.telegram_enabled:
            self._notifier = start_surge_notifications(self.state)
            if self._notifier.enabled:
                self.console.print("[dim green]Alertas Telegram de subidas fuertes activas.[/]", highlight=False)

    def run_live(self, source: str = "binance") -> None:
        log.info("starting live dashboard source=%s", source)
        self._print_startup_banner(source, "LIVE")
        self.console.print(
            f"[bold bright_green]AZ TERMINAL v3.2[/] iniciando WebSocket [{source}]...",
            highlight=False,
        )
        self.start_streams(source)
        self._warmup(source)
        self._start_background_services()

        def shutdown(sig, frame):
            log.info("shutting down")
            self.console.print("\n[dim green]Cerrando streams...[/]")
            if self._stream:
                self._stream.stop()
            if self._focus:
                self._focus.stop()
            if self._notifier:
                self._notifier.stop()
            if self._tick_store:
                self._tick_store.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        time.sleep(1.5)
        try:
            with Live(
                build_dashboard(self.state.snapshot(), self.view, self.selected_symbol, self.portfolio_eval()),
                refresh_per_second=self.settings.refresh_per_second,
                screen=True,
            ) as live:
                while True:
                    time.sleep(0.5)
                    self._handle_key(self._read_key())
                    live.update(build_dashboard(self.state.snapshot(), self.view, self.selected_symbol, self.portfolio_eval()))
        except Exception as e:
            log.exception("live dashboard crashed")
            self.console.print(f"[red]Error: {e}[/]")
        finally:
            if self._tick_store:
                self._tick_store.stop()

    def run_backtest(self, symbol: str, source: str = "binance", interval: int = 60, limit: int = 500, allow_short: bool = True) -> int:
        """Fetch history for ``symbol`` and print a backtest report. Returns exit code."""
        from rich.table import Table
        from rich import box
        from .backtest import BacktestConfig, run_backtest

        symbol = symbol.upper()
        self.console.print(f"[bold bright_green]BACKTEST[/] {symbol} · {source} · {interval}s · {limit} velas")
        candles = fetch_candles(symbol, source=source, interval=interval, limit=limit)
        if len(candles) < 60:
            self.console.print(f"[red]Datos insuficientes para {symbol} ({len(candles)} velas).[/]")
            return 1

        cfg = BacktestConfig(allow_short=allow_short)
        result = run_backtest(candles, cfg)

        ret = result["return_pct"]
        bh = result["buy_hold_pct"]
        edge = ret - bh
        ret_col = "bright_green" if ret >= 0 else "bright_red"
        edge_col = "bright_green" if edge >= 0 else "bright_red"

        tbl = Table(box=box.SIMPLE_HEAVY, border_style="dark_green", header_style="bold bright_green", expand=False)
        tbl.add_column("MÉTRICA", style="dim green")
        tbl.add_column("VALOR", justify="right")
        tbl.add_row("Velas evaluadas", f"{result['bars']:,}")
        tbl.add_row("Estrategia", f"[{ret_col}]{ret:+.2f}%[/]")
        tbl.add_row("Buy & Hold", f"{bh:+.2f}%")
        tbl.add_row("Edge vs B&H", f"[{edge_col}]{edge:+.2f}%[/]")
        tbl.add_row("Operaciones", f"{result['trades']}  ({result['wins']}W / {result['losses']}L)")
        tbl.add_row("Win rate", f"{result['win_rate']:.1f}%")
        tbl.add_row("Ganancia media", f"{result['avg_win_pct']:+.3f}%")
        tbl.add_row("Pérdida media", f"{result['avg_loss_pct']:+.3f}%")
        tbl.add_row("Max drawdown", f"[bright_red]{result['max_drawdown_pct']:.2f}%[/]")
        tbl.add_row("Sharpe (anual.)", f"{result['sharpe']:.2f}")
        tbl.add_row("Exposición", f"{result['exposure_pct']:.1f}%")
        self.console.print(tbl)

        if result["trade_log"]:
            log_tbl = Table(box=box.SIMPLE, border_style="dark_green", header_style="bold bright_green", title="[dim]últimas operaciones[/]")
            log_tbl.add_column("LADO")
            log_tbl.add_column("ENTRADA", justify="right")
            log_tbl.add_column("SALIDA", justify="right")
            log_tbl.add_column("VELAS", justify="right")
            log_tbl.add_column("P&L%", justify="right")
            for t in result["trade_log"]:
                pnl = t["pnl_pct"]
                col = "bright_green" if pnl >= 0 else "bright_red"
                side_col = "green" if t["side"] == "LONG" else "red"
                log_tbl.add_row(
                    f"[{side_col}]{t['side']}[/]",
                    f"{t['entry']:g}", f"{t['exit']:g}",
                    str(t["bars"]), f"[{col}]{pnl:+.3f}%[/]",
                )
            self.console.print(log_tbl)
        self.console.print("[dim]No es asesoría financiera. Rendimiento pasado no garantiza resultados futuros.[/]")
        return 0

    def run_once(
        self,
        source: str = "binance",
        output_format: str = "table",
        output_path: str | None = None,
        symbols: list[str] | None = None,
        scan: str | None = None,
        limit: int = 10,
    ) -> None:
        log.info("starting snapshot source=%s", source)
        if output_format == "table":
            self._print_startup_banner(source, "SNAPSHOT")
            self.console.print("[bold bright_green]AZ TERMINAL - SNAPSHOT[/]")
        self.start_streams(source)
        self._warmup(source)
        if output_format == "table":
            self._start_background_services()
        time.sleep(4)
        snapshot = self.state.snapshot()
        if output_format == "table":
            if scan:
                self.console.print(render_scan_table(scan_snapshot(snapshot, scan, limit, symbols), scan))
            else:
                self.console.print(build_dashboard(snapshot, self.view, self.selected_symbol, self.portfolio_eval()))
        else:
            content = (
                render_scan(snapshot, output_format, scan, limit, symbols)
                if scan
                else render_snapshot(snapshot, output_format, symbols)
            )
            if output_path:
                write_snapshot(output_path, content)
                self.console.print(f"[bright_green]Snapshot guardado:[/] {output_path}", highlight=False)
            else:
                self.console.print(content, markup=False, highlight=False)
        if self._stream:
            self._stream.stop()
        if self._notifier:
            self._notifier.stop()
        if self._tick_store:
            self._tick_store.stop()

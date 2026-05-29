from __future__ import annotations

import logging
import signal
import sys
import time
from typing import Optional

from rich.console import Console
from rich.live import Live

from .config import HELP_TEXT, SYMBOLS_ORDERED
from .dashboard import build_dashboard
from .notifications import start_surge_notifications
from .rest import start_rest
from .settings import AppSettings
from .state import MarketState
from .storage import SQLiteTickStore
from .streams import BinanceStream, CoinbaseStream, KrakenStream

log = logging.getLogger(__name__)


class CryptexApp:
    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or AppSettings()
        self._tick_store = None
        if self.settings.sqlite_enabled:
            self._tick_store = SQLiteTickStore(self.settings.sqlite_path, self.settings.sqlite_batch_size)
            self._tick_store.start()
        self.state = MarketState(tick_recorder=self._tick_store)
        self._stream = None
        self._notifier = None
        self.console = Console()
        self.view = self.settings.initial_view
        self.selected_symbol = self.settings.selected_symbol

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

    def start_streams(self, source: str) -> None:
        if source == "coinbase":
            self._stream = CoinbaseStream(self.state)
        elif source == "kraken":
            self._stream = KrakenStream(self.state)
        else:
            self._stream = BinanceStream(self.state)
        self._stream.start()

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
        self.console.print(
            f"[bold bright_green]AZ TERMINAL v3.2[/] iniciando WebSocket [{source}]...",
            highlight=False,
        )
        self.start_streams(source)
        self._start_background_services()

        def shutdown(sig, frame):
            log.info("shutting down")
            self.console.print("\n[dim green]Cerrando streams...[/]")
            if self._stream:
                self._stream.stop()
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
                build_dashboard(self.state.snapshot(), self.view, self.selected_symbol),
                refresh_per_second=self.settings.refresh_per_second,
                screen=True,
            ) as live:
                while True:
                    time.sleep(0.5)
                    self._handle_key(self._read_key())
                    live.update(build_dashboard(self.state.snapshot(), self.view, self.selected_symbol))
        except Exception as e:
            log.exception("live dashboard crashed")
            self.console.print(f"[red]Error: {e}[/]")
        finally:
            if self._tick_store:
                self._tick_store.stop()

    def run_once(self, source: str = "binance") -> None:
        log.info("starting snapshot source=%s", source)
        self.console.print("[bold bright_green]AZ TERMINAL - SNAPSHOT[/]")
        self.start_streams(source)
        self._start_background_services()
        time.sleep(4)
        self.console.print(build_dashboard(self.state.snapshot(), self.view, self.selected_symbol))
        if self._stream:
            self._stream.stop()
        if self._notifier:
            self._notifier.stop()
        if self._tick_store:
            self._tick_store.stop()

from __future__ import annotations

import signal
import sys
import time
from typing import Optional

from rich.console import Console
from rich.live import Live

from .config import HELP_TEXT
from .dashboard import build_dashboard
from .notifications import start_surge_notifications
from .rest import start_rest
from .state import MarketState
from .streams import BinanceStream, CoinbaseStream, KrakenStream


class CryptexApp:
    def __init__(self):
        self.state = MarketState()
        self._stream = None
        self._notifier = None
        self.console = Console()
        self.view = "markets"

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

    def start_streams(self, source: str):
        if source == "coinbase":
            self._stream = CoinbaseStream(self.state)
            self._stream.start()
        elif source == "kraken":
            self._stream = KrakenStream(self.state)
            self._stream.start()
        else:
            self._stream = BinanceStream(self.state)
            self._stream.start()

    def run_live(self, source: str = "binance"):
        self.console.print(
            f"[bold bright_green]◈ AZ TERMINAL v3.2[/] iniciando WebSocket [{source}]...",
            highlight=False,
        )
        self.start_streams(source)
        start_rest(self.state)
        self._notifier = start_surge_notifications(self.state)
        if self._notifier.enabled:
            self.console.print("[dim green]Alertas Telegram de subidas fuertes activas.[/]", highlight=False)

        def shutdown(sig, frame):
            self.console.print("\n[dim green]Cerrando streams...[/]")
            if self._stream:
                self._stream.stop()
            if self._notifier:
                self._notifier.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        time.sleep(1.5)
        try:
            with Live(build_dashboard(self.state.snapshot(), self.view), refresh_per_second=2, screen=True) as live:
                while True:
                    time.sleep(0.5)
                    self._handle_key(self._read_key())
                    live.update(build_dashboard(self.state.snapshot(), self.view))
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/]")

    def run_once(self, source: str = "binance"):
        self.console.print("[bold bright_green]◈ AZ TERMINAL — SNAPSHOT[/]")
        self.start_streams(source)
        start_rest(self.state)
        self._notifier = start_surge_notifications(self.state)
        time.sleep(4)
        self.console.print(build_dashboard(self.state.snapshot(), self.view))

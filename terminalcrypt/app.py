from __future__ import annotations

import signal
import sys
import time

from rich.console import Console
from rich.live import Live

from .config import HELP_TEXT
from .dashboard import build_dashboard
from .rest import start_rest
from .state import MarketState
from .streams import BinanceStream, CoinbaseStream, KrakenStream


class CryptexApp:
    def __init__(self):
        self.state = MarketState()
        self._stream = None
        self.console = Console()

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

        def shutdown(sig, frame):
            self.console.print("\n[dim green]Cerrando streams...[/]")
            if self._stream:
                self._stream.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, shutdown)
        signal.signal(signal.SIGTERM, shutdown)

        time.sleep(1.5)
        try:
            with Live(build_dashboard(self.state.snapshot()), refresh_per_second=2, screen=True) as live:
                while True:
                    time.sleep(0.5)
                    live.update(build_dashboard(self.state.snapshot()))
        except Exception as e:
            self.console.print(f"[red]Error: {e}[/]")

    def run_once(self, source: str = "binance"):
        self.console.print("[bold bright_green]◈ AZ TERMINAL — SNAPSHOT[/]")
        self.start_streams(source)
        start_rest(self.state)
        time.sleep(4)
        self.console.print(build_dashboard(self.state.snapshot()))

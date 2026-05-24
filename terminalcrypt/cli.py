from __future__ import annotations

import argparse

from .app import CryptexApp
from .config import HELP_TEXT


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", default="binance", choices=["binance", "coinbase", "kraken"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--alert", nargs=2, metavar=("SYM", "PRICE"))
    parser.add_argument("--help", action="store_true")
    args = parser.parse_args()

    app = CryptexApp()
    if args.help:
        app.console.print(HELP_TEXT)
    elif args.alert:
        sym, price_str = args.alert
        try:
            with app.state._lock:
                app.state.alerts[sym.upper()] = float(price_str)
            app.console.print(f"[bright_green]Alerta:[/] {sym.upper()} ≥ ${float(price_str):,.2f}")
            app.run_live(args.source)
        except ValueError:
            app.console.print("[red]Precio inválido.[/]")
    elif args.once:
        app.run_once(args.source)
    else:
        app.run_live(args.source)

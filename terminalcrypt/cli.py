from __future__ import annotations

import argparse
import dataclasses
import sys
from pathlib import Path

from . import __version__
from .app import CryptexApp
from .config import HELP_TEXT
from .export import parse_symbols
from .scanner import SCAN_MODES
from .settings import configure_logging, load_settings


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    settings = load_settings()
    configure_logging(settings)
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", default=settings.source, choices=["binance", "coinbase", "kraken"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--format", default="table", choices=["table", "json", "csv"])
    parser.add_argument("--output")
    parser.add_argument("--symbols")
    parser.add_argument("--scan", choices=SCAN_MODES)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--alert", nargs=2, metavar=("SYM", "PRICE"))
    parser.add_argument("--version", action="version", version=f"terminalcrypt {__version__}")
    parser.add_argument("--backtest", metavar="SYM", help="Backtest de la señal sobre datos históricos y salir")
    parser.add_argument("--interval", type=int, default=60, help="Intervalo de vela en segundos para el backtest (60/300/900/3600)")
    parser.add_argument("--candles", type=int, default=500, help="Número de velas históricas para el backtest")
    parser.add_argument("--long-only", action="store_true", help="Backtest sólo en largo (sin cortos)")
    parser.add_argument("--portfolio", metavar="PATH", help="Carga un portfolio (JSON/TOML) y muestra P&L en vivo")
    parser.add_argument("--radar", action="store_true", help="Abre el Opportunity Radar (scanner multi-factor) en vivo")
    parser.add_argument("--paper", action="store_true", help="Activa paper trading (ejecución simulada)")
    parser.add_argument("--paper-cash", type=float, metavar="USD", help="Efectivo inicial de la cuenta paper")
    parser.add_argument("--paper-reset", action="store_true", help="Reinicia la cuenta paper antes de arrancar")
    parser.add_argument("--paper-export", metavar="CSV", help="Exporta el historial de fills a CSV y sale")
    parser.add_argument("--help", action="store_true")
    args = parser.parse_args()

    overrides = {}
    if args.paper:
        overrides["paper_enabled"] = True
    if args.paper_cash is not None:
        overrides["paper_cash"] = max(0.0, args.paper_cash)
    if overrides:
        settings = dataclasses.replace(settings, **overrides)

    if args.paper_reset:
        try:
            Path(settings.paper_file).unlink(missing_ok=True)
        except OSError:
            pass

    app = CryptexApp(settings)
    if args.portfolio:
        app.load_portfolio(args.portfolio)

    if args.paper_export:
        from .broker import PaperBroker

        broker = app.broker or PaperBroker.load(settings.paper_file, default_cash=settings.paper_cash)
        n = broker.export_fills_csv(args.paper_export)
        app.console.print(f"[bright_green]Exportados {n} fills a[/] {args.paper_export}")
        sys.exit(0)

    if args.help:
        app.console.print(HELP_TEXT)
    elif args.backtest:
        code = app.run_backtest(
            args.backtest,
            source=args.source,
            interval=args.interval,
            limit=args.candles,
            allow_short=not args.long_only,
        )
        sys.exit(code)
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
        app.run_once(
            args.source,
            output_format=args.format,
            output_path=args.output,
            symbols=parse_symbols(args.symbols),
            scan=args.scan,
            limit=max(1, args.limit),
        )
    elif args.portfolio:
        app.view = "portfolio"
        app.run_live(args.source)
    elif args.paper:
        app.view = "broker"
        app.run_live(args.source)
    elif args.radar:
        app.view = "radar"
        app.run_live(args.source)
    else:
        app.run_live(args.source)

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 without an extra TOML dependency.
    tomllib = None


CONFIG_PATH = Path("terminalcrypt.toml")


@dataclass(frozen=True)
class AppSettings:
    source: str = "binance"
    initial_view: str = "markets"
    selected_symbol: str = "BTC"
    refresh_per_second: int = 2
    rest_enabled: bool = True
    telegram_enabled: bool = True
    log_file: str = "logs/terminalcrypt.log"
    log_level: str = "INFO"
    fg_interval: int = 300
    global_interval: int = 120
    news_interval: int = 180


def _coerce(value: Any, current: Any) -> Any:
    if isinstance(current, bool):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
    if isinstance(current, int):
        return int(value)
    return str(value)


def load_settings(path: Path | str = CONFIG_PATH) -> AppSettings:
    data: dict[str, Any] = {}
    path = Path(path)
    if path.exists() and tomllib is not None:
        with path.open("rb") as f:
            payload = tomllib.load(f)
        data.update(payload.get("terminalcrypt", payload))

    defaults = AppSettings()
    values = {field.name: getattr(defaults, field.name) for field in fields(AppSettings)}
    for key, current in list(values.items()):
        if key in data:
            values[key] = _coerce(data[key], current)
        env_key = f"TERMINALCRYPT_{key.upper()}"
        if env_key in os.environ:
            values[key] = _coerce(os.environ[env_key], current)

    if values["source"] not in {"binance", "coinbase", "kraken"}:
        values["source"] = "binance"
    if values["initial_view"] not in {"markets", "top5", "detail"}:
        values["initial_view"] = "markets"
    values["selected_symbol"] = str(values["selected_symbol"]).upper()
    values["refresh_per_second"] = max(1, min(int(values["refresh_per_second"]), 10))
    values["fg_interval"] = max(30, int(values["fg_interval"]))
    values["global_interval"] = max(30, int(values["global_interval"]))
    values["news_interval"] = max(30, int(values["news_interval"]))
    return AppSettings(**values)


def configure_logging(settings: AppSettings) -> None:
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_path,
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        encoding="utf-8",
    )

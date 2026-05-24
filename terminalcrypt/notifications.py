from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone

import requests

from .formatters import fmt_price
from .state import MarketState


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    except OSError:
        return


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class TelegramSurgeNotifier:
    def __init__(self, state: MarketState):
        _load_dotenv()
        self.state = state
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.short_threshold = _env_float("SURGE_ALERT_PCT", 3.0)
        self.day_threshold = _env_float("SURGE_ALERT_24H_PCT", 8.0)
        self.day_short_floor = _env_float("SURGE_ALERT_24H_SHORT_PCT", 1.5)
        self.window = max(3, _env_int("SURGE_ALERT_WINDOW", 12))
        self.cooldown = max(60, _env_int("SURGE_ALERT_COOLDOWN", 900))
        self.interval = max(2, _env_int("SURGE_ALERT_INTERVAL", 5))
        self._last_sent: dict[str, float] = {}
        self._stop = threading.Event()

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.chat_id)

    def start(self) -> bool:
        if not self.enabled:
            return False
        self._stop.clear()
        threading.Thread(target=self._loop, name="telegram-surge-alerts", daemon=True).start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._scan_once()
            self._stop.wait(self.interval)

    def _scan_once(self) -> None:
        now = time.time()
        snapshot = self.state.snapshot()
        for sym, price in snapshot["prices"].items():
            hist = snapshot.get("history", {}).get(sym, [])
            if len(hist) < self.window + 1 or price <= 0:
                continue

            prev = hist[-self.window - 1]
            if prev <= 0:
                continue

            short_pct = (hist[-1] - prev) / prev * 100
            chg24 = snapshot["chg24h"].get(sym, 0)
            short_breakout = short_pct >= self.short_threshold
            day_breakout = chg24 >= self.day_threshold and short_pct >= self.day_short_floor
            if not short_breakout and not day_breakout:
                continue

            if now - self._last_sent.get(sym, 0) < self.cooldown:
                continue

            self._last_sent[sym] = now
            self._send_alert(sym, price, short_pct, chg24, snapshot)

    def _send_alert(self, sym: str, price: float, short_pct: float, chg24: float, snapshot: dict) -> None:
        source = snapshot.get("ws_source", "-")
        ticks = snapshot.get("tick_count", {}).get(sym, 0)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        text = (
            f"AZ TERMINAL - subida fuerte detectada\n"
            f"{sym} {fmt_price(price).strip()}\n"
            f"Subida corta: +{short_pct:.2f}% en {self.window} ticks\n"
            f"24h: {chg24:+.2f}%\n"
            f"Fuente: {source} | ticks: {ticks}\n"
            f"{ts}"
        )
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                timeout=10,
            )
            r.raise_for_status()
            with self.state._lock:
                self.state.errors.pop("telegram", None)
        except Exception as e:
            with self.state._lock:
                self.state.errors["telegram"] = str(e)[:60]


def start_surge_notifications(state: MarketState) -> TelegramSurgeNotifier:
    notifier = TelegramSurgeNotifier(state)
    notifier.start()
    return notifier

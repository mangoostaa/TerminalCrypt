from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

HISTORY_MAX = 120

class MarketState:
    def __init__(self):
        self._lock = threading.Lock()
        self.prices: dict = {}
        self.prev: dict = {}
        self.chg24h: dict = {}
        self.high24: dict = {}
        self.low24: dict = {}
        self.vol24: dict = {}
        self.bid: dict = {}
        self.ask: dict = {}
        self.spread: dict = {}

        self.history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.volume_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.high_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.low_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))

        self.tick_count: dict = defaultdict(int)
        self.last_tick: dict = {}
        self.latency_ms: dict = {}

        self.fg_data: list = []
        self.ws_source: str = "─"
        self.ws_status: str = "connecting"
        self.ws_ticks: int = 0
        self.ws_since: str = "─"
        self.ws_reconnects: int = 0

        self.alerts: dict = {}
        self.triggered: list = []

        self.global_data: dict = {}
        self.global_upd: str = "─"
        self.news: list = []
        self.news_upd: str = "─"

        self.errors: dict = {}

    def update_tick(
        self,
        sym: str,
        price: float,
        chg24: float,
        high: float,
        low: float,
        vol: float,
        bid: float = 0,
        ask: float = 0,
        latency_ms: float = 0,
    ):
        with self._lock:
            self.prev[sym] = self.prices.get(sym, price)
            self.prices[sym] = price
            self.chg24h[sym] = chg24
            self.high24[sym] = high
            self.low24[sym] = low
            self.vol24[sym] = vol

            if bid:
                self.bid[sym] = bid
            if ask:
                self.ask[sym] = ask
            if bid and ask and ask > 0:
                self.spread[sym] = (ask - bid) / ask * 100

            self.history[sym].append(price)
            self.volume_history[sym].append(vol)
            if high:
                self.high_history[sym].append(high)
            if low:
                self.low_history[sym].append(low)

            self.tick_count[sym] += 1
            self.ws_ticks += 1
            self.last_tick[sym] = datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]
            if latency_ms:
                self.latency_ms[sym] = latency_ms

        self._check_alert(sym, price)

    def _check_alert(self, sym: str, price: float):
        target = self.alerts.get(sym)
        if target and price >= target:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            with self._lock:
                self.triggered.append((ts, f"{sym} ≥ ${target:,.0f}"))
                del self.alerts[sym]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "prices": dict(self.prices),
                "prev": dict(self.prev),
                "chg24h": dict(self.chg24h),
                "high24": dict(self.high24),
                "low24": dict(self.low24),
                "vol24": dict(self.vol24),
                "bid": dict(self.bid),
                "ask": dict(self.ask),
                "spread": dict(self.spread),
                "history": {k: list(v) for k, v in self.history.items()},
                "volume_history": {k: list(v) for k, v in self.volume_history.items()},
                "high_history": {k: list(v) for k, v in self.high_history.items()},
                "low_history": {k: list(v) for k, v in self.low_history.items()},
                "tick_count": dict(self.tick_count),
                "last_tick": dict(self.last_tick),
                "latency_ms": dict(self.latency_ms),
                "ws_source": self.ws_source,
                "ws_status": self.ws_status,
                "ws_ticks": self.ws_ticks,
                "ws_since": self.ws_since,
                "ws_reconnects": self.ws_reconnects,
                "fg_data": list(self.fg_data),
                "alerts": dict(self.alerts),
                "triggered": list(self.triggered[-5:]),
                "global": dict(self.global_data),
                "global_upd": self.global_upd,
                "news": list(self.news),
                "news_upd": self.news_upd,
                "errors": dict(self.errors),
            }

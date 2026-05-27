from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import datetime, timezone

HISTORY_MAX = 120
CANDLE_INTERVALS = (60, 300)

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
        self.open_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.candle_history: dict = defaultdict(lambda: deque(maxlen=HISTORY_MAX))
        self.candles: dict = {
            interval: defaultdict(lambda: deque(maxlen=HISTORY_MAX))
            for interval in CANDLE_INTERVALS
        }
        self._active_candles: dict = {interval: {} for interval in CANDLE_INTERVALS}
        self._last_volume: dict = {}
        self.volume_delta: dict = {}

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

    def set_error(self, key: str, err: object, limit: int = 80) -> None:
        msg = f"{type(err).__name__}: {err}" if isinstance(err, Exception) else str(err)
        with self._lock:
            self.errors[key] = msg[:limit]

    def clear_error(self, key: str) -> None:
        with self._lock:
            self.errors.pop(key, None)

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
        open_price: float | None = None,
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

            tick_dt = datetime.now(timezone.utc)
            tick_ts = tick_dt.strftime("%H:%M:%S.%f")[:-3]
            prev_vol = self._last_volume.get(sym)
            vol_delta = max(vol - prev_vol, 0.0) if prev_vol is not None and vol >= prev_vol else 0.0
            self._last_volume[sym] = vol
            self.volume_delta[sym] = vol_delta
            self.history[sym].append(price)
            self.volume_history[sym].append(vol_delta)
            candle_open = open_price if open_price and open_price > 0 else self.prev[sym]
            candle_high = high if high and high > 0 else max(candle_open, price)
            candle_low = low if low and low > 0 else min(candle_open, price)
            self.open_history[sym].append(candle_open)
            self.high_history[sym].append(candle_high)
            self.low_history[sym].append(candle_low)
            self.candle_history[sym].append({
                "open": candle_open,
                "high": candle_high,
                "low": candle_low,
                "close": price,
                "volume": vol,
                "ts": tick_ts,
            })
            self._update_timeframe_candles(sym, price, vol_delta, tick_dt)

            self.tick_count[sym] += 1
            self.ws_ticks += 1
            self.last_tick[sym] = tick_ts
            if latency_ms:
                self.latency_ms[sym] = latency_ms

        self._check_alert(sym, price)

    def _update_timeframe_candles(self, sym: str, price: float, volume: float, tick_dt: datetime) -> None:
        epoch = int(tick_dt.timestamp())
        for interval in CANDLE_INTERVALS:
            bucket = epoch - (epoch % interval)
            active = self._active_candles[interval].get(sym)
            if active is None or active["bucket"] != bucket:
                if active is not None:
                    self.candles[interval][sym].append(active)
                self._active_candles[interval][sym] = {
                    "bucket": bucket,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": volume,
                    "ts": datetime.fromtimestamp(bucket, timezone.utc).strftime("%H:%M:%S"),
                }
                continue
            active["high"] = max(active["high"], price)
            active["low"] = min(active["low"], price)
            active["close"] = price
            active["volume"] += volume

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
                "open_history": {k: list(v) for k, v in self.open_history.items()},
                "high_history": {k: list(v) for k, v in self.high_history.items()},
                "low_history": {k: list(v) for k, v in self.low_history.items()},
                "candle_history": {k: list(v) for k, v in self.candle_history.items()},
                "candles": {
                    interval: {
                        sym: list(rows) + ([self._active_candles[interval][sym]] if sym in self._active_candles[interval] else [])
                        for sym, rows in {
                            **by_symbol,
                            **{active_sym: deque(maxlen=HISTORY_MAX) for active_sym in self._active_candles[interval]},
                        }.items()
                    }
                    for interval, by_symbol in self.candles.items()
                },
                "volume_delta": dict(self.volume_delta),
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

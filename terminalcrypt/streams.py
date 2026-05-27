from __future__ import annotations

import json
import logging
import time
import threading
import websocket

from .config import (
    BINANCE_SYMBOLS,
    BINANCE_WS_ALT,
    BINANCE_WS_URL,
    COINBASE_SYMBOLS,
    COINBASE_WS_URL,
    KRAKEN_SYMBOLS,
    KRAKEN_WS_URL,
)
from .formatters import now_utc
from .state import MarketState

log = logging.getLogger(__name__)


class BinanceStream:
    def __init__(self, state: MarketState):
        self.state = state
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._reconnect_delay = 2

    def _stream_url(self, port: int = 9443) -> str:
        streams = "/".join(f"{sym.lower()}@miniTicker" for sym in BINANCE_SYMBOLS)
        return f"wss://stream.binance.com:{port}/stream?streams={streams}"

    def _on_open(self, ws):
        with self.state._lock:
            self.state.ws_source = "Binance"
            self.state.ws_status = "connected ✓"
            self.state.ws_since = now_utc()
            self.state.errors.pop("binance_ws", None)
        self._reconnect_delay = 2

    def _on_message(self, ws, raw: str):
        try:
            t0 = time.perf_counter()
            msg = json.loads(raw)
            data = msg.get("data", msg)
            sym_raw = data.get("s", "")
            sym = BINANCE_SYMBOLS.get(sym_raw)
            if not sym:
                return
            price = float(data["c"])
            open_price = float(data.get("o", price) or price)
            chg24 = float(data["P"])
            high = float(data["h"])
            low = float(data["l"])
            vol = float(data["v"])
            lat_ms = (time.perf_counter() - t0) * 1000
            self.state.update_tick(sym, price, chg24, high, low, vol, latency_ms=lat_ms, open_price=open_price)
            self.state.clear_error("binance_msg")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            self.state.set_error("binance_msg", e)

    def _on_error(self, ws, err):
        log.warning("binance websocket error: %s", err)
        with self.state._lock:
            self.state.ws_status = f"error: {str(err)[:30]}"
        self.state.set_error("binance_ws", err)

    def _on_close(self, ws, code, reason):
        with self.state._lock:
            self.state.ws_status = "disconnected — reconnecting..."
            self.state.ws_reconnects += 1

    def start(self, port: int = 9443):
        self._stop_flag.clear()

        def _run():
            alt_port = 443 if port == 9443 else 9443
            url = self._stream_url(port)
            while not self._stop_flag.is_set():
                with self.state._lock:
                    self.state.ws_status = f"connecting ({url[:40]}...)"
                self._ws = websocket.WebSocketApp(
                    url,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10, reconnect=0)
                if self._stop_flag.is_set():
                    break
                time.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)
                url = self._stream_url(alt_port if self._reconnect_delay > 4 else port)

        self._thread = threading.Thread(target=_run, name="binance-ws", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag.set()
        if self._ws:
            self._ws.close()


class CoinbaseStream:
    def __init__(self, state: MarketState):
        self.state = state
        self._ws = None
        self._stop = threading.Event()
        self._delay = 2

    def _subscribe_msg(self) -> str:
        return json.dumps({
            "type": "subscribe",
            "product_ids": list(COINBASE_SYMBOLS.keys()),
            "channel": "ticker",
        })

    def _on_open(self, ws):
        ws.send(self._subscribe_msg())
        with self.state._lock:
            self.state.ws_source = "Coinbase"
            self.state.ws_status = "connected ✓"
            self.state.ws_since = now_utc()
            self.state.errors.pop("coinbase_ws", None)
        self._delay = 2

    def _on_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
            if msg.get("channel") != "ticker":
                return
            for event in msg.get("events", []):
                for tick in event.get("tickers", []):
                    prod = tick.get("product_id", "")
                    sym = COINBASE_SYMBOLS.get(prod)
                    if not sym:
                        continue
                    price = float(tick.get("price", 0) or 0)
                    chg24 = float(tick.get("price_percent_chg_24h", 0) or 0)
                    high = float(tick.get("high_52_week", 0) or 0)
                    low = float(tick.get("low_52_week", 0) or 0)
                    vol = float(tick.get("volume_24h", 0) or 0)
                    bid = float(tick.get("best_bid", 0) or 0)
                    ask = float(tick.get("best_ask", 0) or 0)
                    self.state.update_tick(sym, price, chg24, high, low, vol, bid, ask)
            self.state.clear_error("coinbase_msg")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            self.state.set_error("coinbase_msg", e)

    def _on_error(self, ws, err):
        log.warning("coinbase websocket error: %s", err)
        with self.state._lock:
            self.state.ws_status = f"error: {str(err)[:30]}"
        self.state.set_error("coinbase_ws", err)

    def _on_close(self, ws, code, reason):
        with self.state._lock:
            self.state.ws_status = "disconnected — reconnecting..."
            self.state.ws_reconnects += 1

    def start(self):
        self._stop.clear()

        def _run():
            while not self._stop.is_set():
                self._ws = websocket.WebSocketApp(
                    COINBASE_WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
                if self._stop.is_set():
                    break
                time.sleep(self._delay)
                self._delay = min(self._delay * 2, 60)

        threading.Thread(target=_run, name="coinbase-ws", daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._ws:
            self._ws.close()


class KrakenStream:
    def __init__(self, state: MarketState):
        self.state = state
        self._ws = None
        self._stop = threading.Event()
        self._delay = 2

    def _subscribe_msg(self) -> str:
        return json.dumps({
            "method": "subscribe",
            "params": {
                "channel": "ticker",
                "symbol": list(KRAKEN_SYMBOLS.keys()),
            },
        })

    def _on_open(self, ws):
        ws.send(self._subscribe_msg())
        with self.state._lock:
            self.state.ws_source = "Kraken"
            self.state.ws_status = "connected ✓"
            self.state.ws_since = now_utc()
            self.state.errors.pop("kraken_ws", None)
        self._delay = 2

    def _on_message(self, ws, raw: str):
        try:
            msg = json.loads(raw)
            if msg.get("channel") != "ticker":
                return
            for d in msg.get("data", []):
                pair = d.get("symbol", "")
                sym = KRAKEN_SYMBOLS.get(pair)
                if not sym:
                    continue
                price = float(d.get("last", 0) or 0)
                chg24 = float(d.get("change_pct", 0) or 0)
                high = float(d.get("high", 0) or 0)
                low = float(d.get("low", 0) or 0)
                vol = float(d.get("volume", 0) or 0)
                bid = float(d.get("bid", 0) or 0)
                ask = float(d.get("ask", 0) or 0)
                self.state.update_tick(sym, price, chg24, high, low, vol, bid, ask)
            self.state.clear_error("kraken_msg")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as e:
            self.state.set_error("kraken_msg", e)

    def _on_error(self, ws, err):
        log.warning("kraken websocket error: %s", err)
        with self.state._lock:
            self.state.ws_status = f"error: {str(err)[:30]}"
        self.state.set_error("kraken_ws", err)

    def _on_close(self, ws, *args):
        with self.state._lock:
            self.state.ws_status = "disconnected — reconnecting..."
            self.state.ws_reconnects += 1

    def start(self):
        self._stop.clear()

        def _run():
            while not self._stop.is_set():
                self._ws = websocket.WebSocketApp(
                    KRAKEN_WS_URL,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                )
                self._ws.run_forever(ping_interval=20, ping_timeout=10)
                if self._stop.is_set():
                    break
                time.sleep(self._delay)
                self._delay = min(self._delay * 2, 60)

        threading.Thread(target=_run, name="kraken-ws", daemon=True).start()

    def stop(self):
        self._stop.set()
        if self._ws:
            self._ws.close()

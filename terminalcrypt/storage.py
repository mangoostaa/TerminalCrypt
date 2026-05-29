from __future__ import annotations

import logging
import queue
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickRecord:
    symbol: str
    price: float
    change_24h: float
    high_24h: float
    low_24h: float
    volume_24h: float
    bid: float
    ask: float
    spread: float
    volume_delta: float
    latency_ms: float
    source: str
    observed_at: str


class SQLiteTickStore:
    def __init__(self, path: str | Path, batch_size: int = 100):
        self.path = Path(path)
        self.batch_size = max(1, batch_size)
        self._queue: queue.Queue[TickRecord | None] = queue.Queue(maxsize=10_000)
        self._thread = threading.Thread(target=self._run, name="SQLiteTickStore", daemon=True)

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._thread.start()

    def record_tick(self, tick: TickRecord) -> None:
        try:
            self._queue.put_nowait(tick)
        except queue.Full:
            log.warning("sqlite tick queue is full; dropping tick symbol=%s", tick.symbol)

    def stop(self, timeout: float = 5.0) -> None:
        if not self._thread.is_alive():
            return
        try:
            self._queue.put(None, timeout=timeout)
        except queue.Full:
            pass
        self._thread.join(timeout=timeout)

    def _run(self) -> None:
        conn: sqlite3.Connection | None = None
        try:
            conn = sqlite3.connect(self.path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._init_schema(conn)
            self._drain(conn)
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            log.exception("sqlite persistence stopped")
        finally:
            if conn is not None:
                conn.close()

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ticks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                observed_at TEXT NOT NULL,
                source TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                change_24h REAL NOT NULL,
                high_24h REAL NOT NULL,
                low_24h REAL NOT NULL,
                volume_24h REAL NOT NULL,
                bid REAL NOT NULL,
                ask REAL NOT NULL,
                spread REAL NOT NULL,
                volume_delta REAL NOT NULL,
                latency_ms REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticks_symbol_time ON ticks(symbol, observed_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticks_source_time ON ticks(source, observed_at)")
        conn.commit()

    def _drain(self, conn: sqlite3.Connection) -> None:
        batch: list[TickRecord] = []
        while True:
            item = self._queue.get()

            if item is None:
                if batch:
                    self._insert_batch(conn, batch)
                return

            batch.append(item)
            if len(batch) >= self.batch_size:
                self._insert_batch(conn, batch)
                batch.clear()

    def _insert_batch(self, conn: sqlite3.Connection, batch: list[TickRecord]) -> None:
        conn.executemany(
            """
            INSERT INTO ticks (
                observed_at, source, symbol, price, change_24h, high_24h, low_24h,
                volume_24h, bid, ask, spread, volume_delta, latency_ms
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    tick.observed_at,
                    tick.source,
                    tick.symbol,
                    tick.price,
                    tick.change_24h,
                    tick.high_24h,
                    tick.low_24h,
                    tick.volume_24h,
                    tick.bid,
                    tick.ask,
                    tick.spread,
                    tick.volume_delta,
                    tick.latency_ms,
                )
                for tick in batch
            ],
        )
        conn.commit()

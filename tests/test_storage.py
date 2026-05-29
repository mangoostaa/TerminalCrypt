from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from terminalcrypt.state import MarketState
from terminalcrypt.storage import SQLiteTickStore


class SQLiteStorageTests(unittest.TestCase):
    def test_tick_store_persists_market_ticks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ticks.sqlite3"
            store = SQLiteTickStore(path, batch_size=1)
            store.start()
            state = MarketState(tick_recorder=store)
            state.ws_source = "test"

            state.update_tick(
                "BTC",
                price=100.0,
                chg24=1.5,
                high=110.0,
                low=90.0,
                vol=1234.0,
                bid=99.5,
                ask=100.5,
                latency_ms=12.0,
            )
            store.stop()

            conn = sqlite3.connect(path)
            try:
                row = conn.execute(
                    """
                    SELECT source, symbol, price, change_24h, high_24h, low_24h,
                           volume_24h, bid, ask, spread, latency_ms
                    FROM ticks
                    """
                ).fetchone()
            finally:
                conn.close()

        self.assertEqual(row[0], "test")
        self.assertEqual(row[1], "BTC")
        self.assertEqual(row[2], 100.0)
        self.assertEqual(row[3], 1.5)
        self.assertEqual(row[4], 110.0)
        self.assertEqual(row[5], 90.0)
        self.assertEqual(row[6], 1234.0)
        self.assertEqual(row[7], 99.5)
        self.assertEqual(row[8], 100.5)
        self.assertGreater(row[9], 0.0)
        self.assertEqual(row[10], 12.0)


if __name__ == "__main__":
    unittest.main()

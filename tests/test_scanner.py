from __future__ import annotations

import unittest

from terminalcrypt.scanner import render_scan_table, scan_snapshot
from terminalcrypt.state import MarketState


def _snapshot() -> dict:
    state = MarketState()
    samples = {
        "BTC": (100.0, 5.0, 1000.0),
        "ETH": (200.0, -7.0, 3000.0),
        "SOL": (50.0, 2.0, 5000.0),
    }
    for i in range(35):
        for sym, (base, chg, vol) in samples.items():
            price = base + i
            state.update_tick(sym, price, chg, price + 2, price - 2, vol + i)
    return state.snapshot()


class ScannerTests(unittest.TestCase):
    def test_movers_scan_sorts_by_absolute_change(self):
        rows = scan_snapshot(_snapshot(), "movers", limit=2)
        self.assertEqual([row["symbol"] for row in rows], ["ETH", "BTC"])
        self.assertEqual(rows[0]["rank"], 1)

    def test_volume_scan_can_filter_symbols(self):
        rows = scan_snapshot(_snapshot(), "volume", limit=5, symbols=["BTC", "SOL"])
        self.assertEqual({row["symbol"] for row in rows}, {"BTC", "SOL"})
        self.assertLessEqual(len(rows), 2)

    def test_signals_scan_renders_table(self):
        rows = scan_snapshot(_snapshot(), "signals", limit=3)
        table = render_scan_table(rows, "signals")
        self.assertEqual(table.title, "Scanner: Senales")


if __name__ == "__main__":
    unittest.main()

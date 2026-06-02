from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from terminalcrypt.export import parse_symbols, render_scan, render_snapshot, snapshot_rows, write_snapshot
from terminalcrypt.state import MarketState


def _snapshot() -> dict:
    state = MarketState()
    for i in range(30):
        state.update_tick("BTC", 100.0 + i, 1.5, 130.0, 90.0, 1000.0 + i, bid=128.0, ask=129.0)
        state.update_tick("ETH", 200.0 + i, -0.5, 230.0, 190.0, 2000.0 + i)
    return state.snapshot()


class ExportTests(unittest.TestCase):
    def test_parse_symbols_normalizes_comma_list(self):
        self.assertEqual(parse_symbols(" btc,ETH, sol "), ["BTC", "ETH", "SOL"])
        self.assertIsNone(parse_symbols(""))

    def test_snapshot_rows_filters_symbols(self):
        rows = snapshot_rows(_snapshot(), ["ETH"])
        self.assertEqual([row["symbol"] for row in rows], ["ETH"])
        self.assertIn("price", rows[0])
        self.assertIn("signal", rows[0])

    def test_render_json_snapshot(self):
        payload = json.loads(render_snapshot(_snapshot(), "json", ["BTC"]))
        self.assertEqual(payload["rows"][0]["symbol"], "BTC")
        self.assertEqual(payload["ticks"], 60)

    def test_render_csv_snapshot(self):
        content = render_snapshot(_snapshot(), "csv", ["BTC"])
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(rows[0]["symbol"], "BTC")
        self.assertEqual(rows[0]["price"], "129.0")

    def test_render_scan_json_snapshot(self):
        payload = json.loads(render_scan(_snapshot(), "json", "signals", limit=1, symbols=["BTC"]))
        self.assertEqual(payload["scan"], "signals")
        self.assertEqual(payload["rows"][0]["symbol"], "BTC")

    def test_render_scan_csv_snapshot(self):
        content = render_scan(_snapshot(), "csv", "movers", limit=1, symbols=["BTC"])
        rows = list(csv.DictReader(io.StringIO(content)))
        self.assertEqual(rows[0]["rank"], "1")
        self.assertEqual(rows[0]["symbol"], "BTC")

    def test_render_setups_json_snapshot(self):
        payload = json.loads(render_scan(_snapshot(), "json", "setups", limit=1, symbols=["BTC"]))
        row = payload["rows"][0]
        self.assertEqual(payload["scan"], "setups")
        self.assertEqual(row["symbol"], "BTC")
        self.assertIn(row["side"], {"LONG", "SHORT"})
        self.assertGreater(row["entry"], 0)
        self.assertGreater(row["stop_loss"], 0)
        self.assertGreater(row["take_profit_1"], 0)

    def test_write_snapshot_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "nested" / "snapshot.json"
            write_snapshot(target, "{}")
            self.assertEqual(target.read_text(encoding="utf-8"), "{}\n")


if __name__ == "__main__":
    unittest.main()

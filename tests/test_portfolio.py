from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from terminalcrypt.portfolio import Holding, Portfolio


class PortfolioTests(unittest.TestCase):
    def test_from_dict_skips_malformed_and_zero(self):
        pf = Portfolio.from_dict({
            "holdings": [
                {"symbol": "btc", "quantity": 0.5, "cost_basis": 40000},
                {"symbol": "eth", "quantity": 0, "cost_basis": 3000},   # zero qty -> skipped
                {"symbol": "sol"},                                       # missing qty -> skipped
            ]
        })
        self.assertEqual(len(pf.holdings), 1)
        self.assertEqual(pf.holdings[0].symbol, "BTC")

    def test_evaluate_computes_pnl_and_allocation(self):
        pf = Portfolio([
            Holding("BTC", 1.0, 40000.0),
            Holding("ETH", 10.0, 3000.0),
        ])
        result = pf.evaluate({"BTC": 50000.0, "ETH": 2000.0})

        self.assertEqual(result["count"], 2)
        # Total value = 50,000 + 20,000 = 70,000; cost = 40,000 + 30,000 = 70,000.
        self.assertAlmostEqual(result["total_value"], 70000.0)
        self.assertAlmostEqual(result["total_cost"], 70000.0)
        self.assertAlmostEqual(result["total_pnl"], 0.0)

        by_sym = {p["symbol"]: p for p in result["positions"]}
        self.assertAlmostEqual(by_sym["BTC"]["pnl"], 10000.0)
        self.assertAlmostEqual(by_sym["BTC"]["pnl_pct"], 25.0)
        self.assertAlmostEqual(by_sym["ETH"]["pnl"], -10000.0)
        self.assertAlmostEqual(by_sym["BTC"]["allocation_pct"], 50000.0 / 70000.0 * 100, places=2)

    def test_missing_price_marks_unpriced(self):
        pf = Portfolio([Holding("XYZ", 5.0, 10.0)])
        result = pf.evaluate({})
        pos = result["positions"][0]
        self.assertFalse(pos["priced"])
        self.assertEqual(pos["value"], 0.0)

    def test_load_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "portfolio.json"
            path.write_text(json.dumps({"holdings": [{"symbol": "BTC", "quantity": 2, "cost_basis": 100}]}), encoding="utf-8")
            pf = Portfolio.load(path)
            self.assertEqual(pf.symbols, ["BTC"])

    def test_load_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            Portfolio.load("does-not-exist-12345.json")


if __name__ == "__main__":
    unittest.main()

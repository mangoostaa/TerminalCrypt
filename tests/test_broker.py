from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from terminalcrypt.broker import OrderError, PaperBroker


class PaperBrokerTests(unittest.TestCase):
    def test_market_buy_updates_cash_and_position(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 0.1, 40_000)
        self.assertAlmostEqual(b.position_qty("BTC"), 0.1)
        self.assertAlmostEqual(b.cash, 10_000 - 4_000)
        self.assertEqual(len(b.fills), 1)

    def test_fee_and_slippage_applied_on_buy(self):
        b = PaperBroker(cash=10_000, fee_pct=0.1, slippage_pct=0.5)
        b.market_order("BTC", "buy", 1, 100)
        # fill price = 100 * 1.005 = 100.5; fee = 100.5 * 0.001 = 0.1005
        self.assertAlmostEqual(b.positions["BTC"]["avg"], 100.5)
        self.assertAlmostEqual(b.cash, 10_000 - 100.5 - 0.1005, places=4)

    def test_sell_realizes_pnl(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 1, 100)
        b.market_order("BTC", "sell", 1, 150)
        self.assertAlmostEqual(b.position_qty("BTC"), 0.0)
        self.assertAlmostEqual(b.positions["BTC"]["realized"], 50.0)
        self.assertAlmostEqual(b.cash, 10_000 + 50.0)

    def test_partial_reduce_keeps_average(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 2, 100)
        b.market_order("BTC", "sell", 1, 120)
        self.assertAlmostEqual(b.position_qty("BTC"), 1.0)
        self.assertAlmostEqual(b.positions["BTC"]["avg"], 100.0)
        self.assertAlmostEqual(b.positions["BTC"]["realized"], 20.0)

    def test_short_then_cover_profits_when_price_falls(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "sell", 1, 100)   # open short
        self.assertAlmostEqual(b.position_qty("BTC"), -1.0)
        ev = b.evaluate({"BTC": 80})
        self.assertAlmostEqual(ev["unrealized"], 20.0)   # short gained as price fell
        b.market_order("BTC", "buy", 1, 80)     # cover
        self.assertAlmostEqual(b.positions["BTC"]["realized"], 20.0)

    def test_flip_long_to_short(self):
        b = PaperBroker(cash=100_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 1, 100)
        b.market_order("BTC", "sell", 3, 120)   # close 1 (+20) and open short 2 @120
        self.assertAlmostEqual(b.position_qty("BTC"), -2.0)
        self.assertAlmostEqual(b.positions["BTC"]["avg"], 120.0)
        self.assertAlmostEqual(b.positions["BTC"]["realized"], 20.0)

    def test_insufficient_cash_rejected(self):
        b = PaperBroker(cash=100, fee_pct=0.0, slippage_pct=0.0)
        with self.assertRaises(OrderError):
            b.market_order("BTC", "buy", 1, 40_000)

    def test_limit_order_fills_when_crossed(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.limit_order("BTC", "buy", 1, 90)
        self.assertEqual(len(b.open_orders), 1)
        self.assertEqual(b.on_prices({"BTC": 95}), [])      # not crossed
        filled = b.on_prices({"BTC": 88})                    # crossed
        self.assertEqual(len(filled), 1)
        self.assertEqual(len(b.open_orders), 0)
        self.assertAlmostEqual(b.position_qty("BTC"), 1.0)

    def test_close_flattens_position(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 0.5, 100)
        order = b.close("BTC", 110)
        self.assertIsNotNone(order)
        self.assertAlmostEqual(b.position_qty("BTC"), 0.0)
        self.assertIsNone(b.close("BTC", 110))   # nothing left

    def test_evaluate_equity_and_pnl(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 1, 100)
        ev = b.evaluate({"BTC": 150})
        self.assertAlmostEqual(ev["equity"], 10_050.0)   # 9,900 cash + 150 value
        self.assertAlmostEqual(ev["unrealized"], 50.0)
        self.assertAlmostEqual(ev["total_pnl"], 50.0)

    def test_market_notional_sizes_by_quote(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_notional("BTC", "buy", 500, 100)
        self.assertAlmostEqual(b.position_qty("BTC"), 5.0)

    def test_persistence_roundtrip(self):
        b = PaperBroker(cash=10_000, fee_pct=0.05, slippage_pct=0.02)
        b.market_order("BTC", "buy", 1, 100)
        b.limit_order("ETH", "buy", 2, 50)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "acct.json"
            b.save(path)
            b2 = PaperBroker.load(path)
        self.assertAlmostEqual(b2.cash, b.cash)
        self.assertAlmostEqual(b2.position_qty("BTC"), 1.0)
        self.assertEqual(len(b2.open_orders), 1)
        self.assertEqual(b2._seq, b._seq)

    def test_load_missing_returns_fresh_account(self):
        b = PaperBroker.load("nonexistent-acct-999.json", default_cash=5_000)
        self.assertAlmostEqual(b.cash, 5_000)
        self.assertEqual(b.positions, {})

    def test_export_fills_csv(self):
        b = PaperBroker(cash=10_000, fee_pct=0.0, slippage_pct=0.0)
        b.market_order("BTC", "buy", 1, 100)
        b.market_order("BTC", "sell", 1, 110)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "fills.csv"
            n = b.export_fills_csv(path)
            content = path.read_text(encoding="utf-8")
        self.assertEqual(n, 2)
        self.assertIn("symbol,side", content)
        self.assertEqual(content.strip().count("\n"), 2)  # header + 2 rows


if __name__ == "__main__":
    unittest.main()

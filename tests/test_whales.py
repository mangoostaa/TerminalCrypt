from __future__ import annotations

import unittest

from terminalcrypt.whales import classify, recent_whales, trade_notional, whale_pressure


def _t(price, qty, side="buy", ts="12:00:00"):
    return {"price": price, "qty": qty, "side": side, "ts": ts}


class WhaleTests(unittest.TestCase):
    def test_classify_tiers(self):
        self.assertEqual(classify(_t(100, 1200), 100_000), "whale")   # 120k
        self.assertEqual(classify(_t(100, 300), 100_000), "large")    # 30k >= 25%
        self.assertEqual(classify(_t(100, 50), 100_000), "normal")    # 5k

    def test_trade_notional(self):
        self.assertAlmostEqual(trade_notional(_t(100, 2.5)), 250.0)
        self.assertEqual(trade_notional({}), 0.0)

    def test_pressure_bias_and_totals(self):
        trades = [
            _t(100, 1500, "buy"),    # 150k whale buy
            _t(100, 1500, "buy"),    # 150k whale buy
            _t(100, 1000, "sell"),   # 100k whale sell
            _t(100, 10, "sell"),     # 1k -> ignored
        ]
        p = whale_pressure(trades, 100_000)
        self.assertEqual(p["count"], 3)
        self.assertAlmostEqual(p["buy_usd"], 300_000)
        self.assertAlmostEqual(p["sell_usd"], 100_000)
        self.assertAlmostEqual(p["net_usd"], 200_000)
        self.assertAlmostEqual(p["bias"], 0.5)
        self.assertIsNotNone(p["biggest"])

    def test_pressure_empty(self):
        p = whale_pressure([_t(100, 1)], 100_000)
        self.assertEqual(p["count"], 0)
        self.assertEqual(p["bias"], 0.0)
        self.assertIsNone(p["biggest"])

    def test_recent_whales_newest_first(self):
        trades = [_t(100, 2000, "buy", "12:00:01"), _t(100, 5, "sell"), _t(100, 3000, "sell", "12:00:03")]
        whales = recent_whales(trades, 100_000, limit=5)
        self.assertEqual(len(whales), 2)
        self.assertEqual(whales[0]["ts"], "12:00:03")   # newest first
        self.assertIn("notional", whales[0])
        self.assertEqual(whales[0]["tier"], "whale")


if __name__ == "__main__":
    unittest.main()

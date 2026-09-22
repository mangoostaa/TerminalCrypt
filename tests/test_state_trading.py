from __future__ import annotations

import unittest

from terminalcrypt.state import DEPTH_LEVELS, TRADES_MAX, MarketState


class StateTradingTests(unittest.TestCase):
    def test_update_trade_appends_and_caps(self):
        state = MarketState()
        for i in range(TRADES_MAX + 10):
            state.update_trade("BTC", 100.0 + i, 1.0, "buy")
        snap = state.snapshot()
        self.assertEqual(len(snap["trades"]["BTC"]), TRADES_MAX)
        self.assertEqual(snap["trades"]["BTC"][-1]["side"], "buy")

    def test_update_trade_rejects_nonpositive(self):
        state = MarketState()
        state.update_trade("BTC", 0, 1, "buy")
        state.update_trade("BTC", 100, 0, "buy")
        self.assertEqual(state.snapshot()["trades"].get("BTC", []), [])

    def test_orderbook_sorted_and_trimmed(self):
        state = MarketState()
        bids = [(100 - i, 1.0) for i in range(DEPTH_LEVELS + 5)]
        asks = [(101 + i, 1.0) for i in range(DEPTH_LEVELS + 5)]
        # Shuffle order to prove sorting.
        state.update_orderbook("BTC", list(reversed(bids)), list(reversed(asks)))
        book = state.snapshot()["orderbook"]["BTC"]
        self.assertEqual(len(book["bids"]), DEPTH_LEVELS)
        self.assertEqual(len(book["asks"]), DEPTH_LEVELS)
        # Bids descending, asks ascending.
        self.assertEqual(book["bids"][0][0], 100)
        self.assertEqual(book["asks"][0][0], 101)
        self.assertTrue(all(book["bids"][i][0] > book["bids"][i + 1][0] for i in range(len(book["bids"]) - 1)))

    def test_orderbook_drops_zero_qty(self):
        state = MarketState()
        state.update_orderbook("BTC", [(100, 0), (99, 2)], [(101, 0), (102, 3)])
        book = state.snapshot()["orderbook"]["BTC"]
        self.assertEqual(book["bids"], [(99.0, 2.0)])
        self.assertEqual(book["asks"], [(102.0, 3.0)])

    def test_derivs_and_liquidations_in_snapshot(self):
        state = MarketState()
        state.update_funding({"BTC": {"funding_rate": 0.01, "mark_price": 60000, "next_funding": 0}})
        state.update_open_interest({"BTC": 12345.0})
        state.add_liquidation({"symbol": "BTC", "side": "long", "price": 60000, "qty": 1, "notional": 60000})
        snap = state.snapshot()
        self.assertAlmostEqual(snap["funding"]["BTC"]["funding_rate"], 0.01)
        self.assertAlmostEqual(snap["open_interest"]["BTC"], 12345.0)
        self.assertEqual(snap["liquidations"][-1]["side"], "long")
        self.assertIn("ts", snap["liquidations"][-1])

    def test_seed_candles_warms_history(self):
        state = MarketState()
        candles = [
            {"open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100.5 + i, "volume": 10, "ts": "00:00:00"}
            for i in range(30)
        ]
        state.seed_candles("BTC", candles)
        snap = state.snapshot()
        self.assertEqual(len(snap["candles"][60]["BTC"]), 30)
        self.assertIn("BTC", snap["prices"])
        # Seeding a symbol that already has candles is a no-op.
        state.seed_candles("BTC", candles)
        self.assertEqual(len(state.snapshot()["candles"][60]["BTC"]), 30)


if __name__ == "__main__":
    unittest.main()

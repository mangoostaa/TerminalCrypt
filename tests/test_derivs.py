from __future__ import annotations

import unittest

from terminalcrypt.derivs import parse_liquidation


class DerivsParseTests(unittest.TestCase):
    def test_liquidated_long_is_forced_sell(self):
        msg = {"e": "forceOrder", "o": {"s": "BTCUSDT", "S": "SELL", "q": "0.5", "ap": "60000"}}
        liq = parse_liquidation(msg)
        self.assertEqual(liq["symbol"], "BTC")
        self.assertEqual(liq["side"], "long")       # forced sell closes a long
        self.assertAlmostEqual(liq["notional"], 30_000.0)

    def test_liquidated_short_is_forced_buy(self):
        msg = {"o": {"s": "ETHUSDT", "S": "BUY", "q": "2", "ap": "3000"}}
        liq = parse_liquidation(msg)
        self.assertEqual(liq["symbol"], "ETH")
        self.assertEqual(liq["side"], "short")
        self.assertAlmostEqual(liq["notional"], 6_000.0)

    def test_unknown_symbol_returns_none(self):
        self.assertIsNone(parse_liquidation({"o": {"s": "FOOBARUSDT", "S": "SELL", "q": "1", "ap": "1"}}))

    def test_zero_values_returns_none(self):
        self.assertIsNone(parse_liquidation({"o": {"s": "BTCUSDT", "S": "SELL", "q": "0", "ap": "60000"}}))

    def test_falls_back_to_price_when_no_avg(self):
        liq = parse_liquidation({"o": {"s": "BTCUSDT", "S": "SELL", "q": "1", "p": "59000"}})
        self.assertAlmostEqual(liq["price"], 59_000.0)


if __name__ == "__main__":
    unittest.main()

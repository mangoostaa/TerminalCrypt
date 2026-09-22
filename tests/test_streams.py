from __future__ import annotations

import json
import unittest

from terminalcrypt.state import MarketState
from terminalcrypt.streams import BinanceFocusStream, BinanceStream, CoinbaseStream, KrakenStream


class FocusStreamParserTests(unittest.TestCase):
    def test_aggtrade_records_taker_side(self):
        state = MarketState()
        stream = BinanceFocusStream(state, "BTC")
        # m=True means the buyer is the maker, so the aggressor sold.
        stream._on_message(None, json.dumps({
            "stream": "btcusdt@aggTrade",
            "data": {"e": "aggTrade", "s": "BTCUSDT", "p": "100.5", "q": "0.25", "m": True},
        }))
        stream._on_message(None, json.dumps({
            "stream": "btcusdt@aggTrade",
            "data": {"e": "aggTrade", "s": "BTCUSDT", "p": "101.0", "q": "0.10", "m": False},
        }))
        trades = state.snapshot()["trades"]["BTC"]
        self.assertEqual(trades[0]["side"], "sell")
        self.assertEqual(trades[1]["side"], "buy")
        self.assertEqual(trades[1]["price"], 101.0)

    def test_depth_populates_orderbook(self):
        state = MarketState()
        stream = BinanceFocusStream(state, "BTC")
        stream._on_message(None, json.dumps({
            "stream": "btcusdt@depth20@100ms",
            "data": {"bids": [["99.5", "2"], ["99.0", "1"]], "asks": [["100.5", "3"], ["101.0", "1"]]},
        }))
        book = state.snapshot()["orderbook"]["BTC"]
        self.assertEqual(book["bids"][0], (99.5, 2.0))
        self.assertEqual(book["asks"][0], (100.5, 3.0))

    def test_set_symbol_clears_stale_book(self):
        state = MarketState()
        stream = BinanceFocusStream(state, "BTC")
        stream._on_message(None, json.dumps({
            "stream": "ethusdt@depth20@100ms",
            "data": {"bids": [["10", "1"]], "asks": [["11", "1"]]},
        }))
        # set_symbol should not raise when there is no live socket and should
        # drop any stale book for the new symbol.
        stream.set_symbol("ETH")
        self.assertNotIn("ETH", state.snapshot()["orderbook"])


class StreamParserTests(unittest.TestCase):
    def test_binance_message_updates_state(self):
        state = MarketState()
        stream = BinanceStream(state)
        payload = {
            "data": {
                "s": "BTCUSDT",
                "c": "100.0",
                "P": "1.5",
                "h": "110.0",
                "l": "90.0",
                "v": "1234.0",
            }
        }
        stream._on_message(None, json.dumps(payload))
        snap = state.snapshot()
        self.assertEqual(snap["prices"]["BTC"], 100.0)
        self.assertEqual(snap["candle_history"]["BTC"][-1]["open"], 100.0)
        self.assertNotIn("binance_msg", snap["errors"])

    def test_binance_miniticker_without_percent_change_updates_state(self):
        state = MarketState()
        stream = BinanceStream(state)
        payload = {
            "data": {
                "s": "BTCUSDT",
                "o": "95.0",
                "c": "100.0",
                "h": "110.0",
                "l": "90.0",
                "v": "1234.0",
            }
        }
        stream._on_message(None, json.dumps(payload))
        snap = state.snapshot()
        self.assertEqual(snap["prices"]["BTC"], 100.0)
        self.assertAlmostEqual(snap["chg24h"]["BTC"], 5.263157894736842)
        self.assertNotIn("binance_msg", snap["errors"])

    def test_coinbase_message_updates_state(self):
        state = MarketState()
        stream = CoinbaseStream(state)
        payload = {
            "channel": "ticker",
            "events": [
                {
                    "tickers": [
                        {
                            "product_id": "BTC-USD",
                            "price": "100.0",
                            "price_percent_chg_24h": "1.5",
                            "high_52_week": "110.0",
                            "low_52_week": "90.0",
                            "volume_24h": "1234.0",
                            "best_bid": "99.5",
                            "best_ask": "100.5",
                        }
                    ]
                }
            ],
        }
        stream._on_message(None, json.dumps(payload))
        snap = state.snapshot()
        self.assertEqual(snap["prices"]["BTC"], 100.0)
        self.assertGreater(snap["spread"]["BTC"], 0)

    def test_kraken_message_updates_state(self):
        state = MarketState()
        stream = KrakenStream(state)
        payload = {
            "channel": "ticker",
            "data": [
                {
                    "symbol": "XBT/USD",
                    "last": "100.0",
                    "change_pct": "1.5",
                    "high": "110.0",
                    "low": "90.0",
                    "volume": "1234.0",
                    "bid": "99.5",
                    "ask": "100.5",
                }
            ],
        }
        stream._on_message(None, json.dumps(payload))
        self.assertEqual(state.snapshot()["prices"]["BTC"], 100.0)

    def test_bad_json_is_reported(self):
        state = MarketState()
        stream = BinanceStream(state)
        stream._on_message(None, "{bad json")
        self.assertIn("binance_msg", state.snapshot()["errors"])


if __name__ == "__main__":
    unittest.main()

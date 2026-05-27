from __future__ import annotations

import json
import unittest

from terminalcrypt.state import MarketState
from terminalcrypt.streams import BinanceStream, CoinbaseStream, KrakenStream


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

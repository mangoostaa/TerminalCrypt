from __future__ import annotations

import unittest

from terminalcrypt import indicators


class IndicatorTests(unittest.TestCase):
    def test_backend_is_available(self):
        self.assertIn(indicators._BACKEND, {"rust", "cython", "python"})

    def test_native_backend_matches_pure_python(self):
        """If a native bundle is loaded, it must agree with pure Python."""
        if indicators._calculate_indicator_bundle_native is None:
            self.skipTest("no native backend loaded")
        prices = [100 + 12 * (i % 17) - 0.3 * i for i in range(120)]
        highs = [p * 1.004 for p in prices]
        lows = [p * 0.996 for p in prices]
        vols = [1000 + (i % 13) * 40 for i in range(120)]
        candles = [{"open": p, "high": h, "low": l, "close": p, "volume": v}
                   for p, h, l, v in zip(prices, highs, lows, vols)]
        native = indicators._calculate_indicator_bundle_native(prices, highs, lows, vols, vols[-1])
        py = indicators._calculate_indicator_bundle_python(prices, highs, lows, vols, candles, vols[-1])
        self.assertAlmostEqual(native["rsi"], py["rsi"], places=1)
        self.assertEqual(native["signal"]["score"], py["signal"]["score"])
        self.assertEqual(native["bb"]["zone"], py["bb"]["zone"])
        self.assertAlmostEqual(native["atr"], py["atr"], places=2)

    def test_core_indicators_return_expected_shapes(self):
        prices = [float(i % 40 + 1) for i in range(80)]
        highs = [p + 1 for p in prices]
        lows = [p - 1 for p in prices]

        self.assertIsInstance(indicators.calculate_rsi(prices), float)
        self.assertEqual(len(indicators.calculate_ema(prices, 9)), len(prices))
        self.assertIn(indicators.calculate_ema_cross(prices)["signal"], {"BULL", "BEAR", "NEUTRAL"})
        self.assertIn("histogram", indicators.calculate_macd(prices))
        self.assertIn("zone", indicators.calculate_bollinger(prices))
        self.assertIsInstance(indicators.calculate_atr(highs, lows, prices), float)
        self.assertEqual(len(indicators.calculate_sma(prices, 20)), len(prices))
        self.assertIsNotNone(indicators.latest_ema(prices, 50))

        candles = [
            {"open": p - 0.5, "high": p + 1, "low": p - 1, "close": p, "volume": 100 + i}
            for i, p in enumerate(prices)
        ]
        self.assertIsInstance(indicators.calculate_vwap(candles), float)
        self.assertIn(indicators.calculate_momentum(prices)["state"], {"BULL", "BEAR", "NEUTRAL"})
        self.assertIn("sma", indicators.calculate_moving_averages(prices))


if __name__ == "__main__":
    unittest.main()

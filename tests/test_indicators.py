from __future__ import annotations

import unittest

from terminalcrypt import indicators


class IndicatorTests(unittest.TestCase):
    def test_backend_is_available(self):
        self.assertIn(indicators._BACKEND, {"rust", "cython", "python"})

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


if __name__ == "__main__":
    unittest.main()

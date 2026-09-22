from __future__ import annotations

import math
import unittest

from terminalcrypt.backtest import BacktestConfig, run_backtest


def _make_candles(closes: list[float]) -> list[dict]:
    candles = []
    for i, c in enumerate(closes):
        prev = closes[i - 1] if i else c
        candles.append({
            "open": prev,
            "high": max(prev, c) * 1.001,
            "low": min(prev, c) * 0.999,
            "close": c,
            "volume": 100.0 + i,
        })
    return candles


class BacktestTests(unittest.TestCase):
    def test_short_series_returns_empty_metrics(self):
        result = run_backtest(_make_candles([1, 2, 3]))
        self.assertEqual(result["trades"], 0)
        self.assertEqual(result["return_pct"], 0.0)
        self.assertEqual(result["bars"], 3)

    def test_result_has_all_metric_keys(self):
        closes = [100 + 10 * math.sin(i / 6) + i * 0.4 for i in range(200)]
        result = run_backtest(_make_candles(closes))
        for key in (
            "trades", "wins", "losses", "win_rate", "return_pct", "buy_hold_pct",
            "max_drawdown_pct", "sharpe", "exposure_pct", "avg_win_pct", "avg_loss_pct",
        ):
            self.assertIn(key, result)
        self.assertIsInstance(result["trade_log"], list)

    def test_uptrend_buy_hold_is_positive(self):
        closes = [100 + i for i in range(200)]
        result = run_backtest(_make_candles(closes))
        self.assertGreater(result["buy_hold_pct"], 0)
        self.assertGreaterEqual(result["max_drawdown_pct"], -100)
        self.assertLessEqual(result["max_drawdown_pct"], 0)

    def test_long_only_never_shorts(self):
        # A steady downtrend: a long-only strategy should not profit from the fall.
        closes = [200 - i * 0.5 for i in range(200)]
        long_only = run_backtest(_make_candles(closes), BacktestConfig(allow_short=False))
        both = run_backtest(_make_candles(closes), BacktestConfig(allow_short=True))
        for t in long_only["trade_log"]:
            self.assertEqual(t["side"], "LONG")
        self.assertLessEqual(long_only["exposure_pct"], 100.0)
        self.assertIn("return_pct", both)

    def test_exposure_within_bounds(self):
        closes = [100 + (i % 20) for i in range(150)]
        result = run_backtest(_make_candles(closes))
        self.assertGreaterEqual(result["exposure_pct"], 0.0)
        self.assertLessEqual(result["exposure_pct"], 100.0)
        self.assertGreaterEqual(result["win_rate"], 0.0)
        self.assertLessEqual(result["win_rate"], 100.0)


if __name__ == "__main__":
    unittest.main()

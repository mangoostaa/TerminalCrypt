from __future__ import annotations

import unittest

from terminalcrypt.analytics import analytics_cache
from terminalcrypt.dashboard import build_dashboard
from terminalcrypt.state import MarketState


class DashboardTests(unittest.TestCase):
    def test_dashboard_views_render_with_synthetic_data(self):
        state = MarketState()
        for i in range(40):
            state.update_tick("BTC", float(100 + i), 1.2, float(101 + i), float(99 + i), 1000 + i)
        snap = state.snapshot()
        self.assertIn("BTC", snap["candles"][60])
        self.assertEqual(snap["candles"][60]["BTC"][-1]["open"], 100.0)
        self.assertEqual(snap["candles"][60]["BTC"][-1]["close"], 139.0)
        build_dashboard(snap, "markets", "BTC")
        build_dashboard(snap, "detail", "BTC")
        build_dashboard(snap, "top5", "BTC")
        self.assertEqual(analytics_cache.intraday_rankings(snap, 1)[0]["sym"], "BTC")
        self.assertEqual(analytics_cache.volume_rankings(snap, 1)[0]["sym"], "BTC")


if __name__ == "__main__":
    unittest.main()

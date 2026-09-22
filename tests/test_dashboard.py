from __future__ import annotations

import unittest

from terminalcrypt.analytics import analytics_cache
from terminalcrypt.dashboard import build_dashboard, panel_alerts
from terminalcrypt.state import MarketState


class DashboardTests(unittest.TestCase):
    def test_dashboard_views_render_with_synthetic_data(self):
        state = MarketState()
        for i in range(40):
            state.update_tick("BTC", float(100 + i), 1.2, float(101 + i), float(99 + i), 1000 + i)
        with state._lock:
            state.alerts["BTC"] = 150.0
            state.triggered.append(("12:00:00", "ETH >= $2,000"))
        snap = state.snapshot()
        self.assertIn("BTC", snap["candles"][60])
        self.assertEqual(snap["candles"][60]["BTC"][-1]["open"], 100.0)
        self.assertEqual(snap["candles"][60]["BTC"][-1]["close"], 139.0)
        state.update_trade("BTC", 139.5, 0.5, "buy")
        state.update_orderbook("BTC", [(139.0, 2.0)], [(140.0, 1.5)])
        snap = state.snapshot()
        layout = build_dashboard(snap, "markets", "BTC")
        self.assertIsNotNone(layout["alerts"])
        panel_alerts(snap)
        build_dashboard(snap, "detail", "BTC")
        build_dashboard(snap, "top5", "BTC")
        # Portfolio view renders both with and without an evaluation.
        build_dashboard(snap, "portfolio", "BTC", None)
        portfolio_eval = {
            "positions": [{
                "symbol": "BTC", "quantity": 0.5, "cost_basis": 100.0, "price": 139.0,
                "value": 69.5, "cost": 50.0, "pnl": 19.5, "pnl_pct": 39.0,
                "allocation_pct": 100.0, "priced": True,
            }],
            "total_value": 69.5, "total_cost": 50.0, "total_pnl": 19.5,
            "total_pnl_pct": 39.0, "count": 1,
        }
        build_dashboard(snap, "portfolio", "BTC", portfolio_eval)
        self.assertEqual(analytics_cache.intraday_rankings(snap, 1)[0]["sym"], "BTC")
        self.assertEqual(analytics_cache.volume_rankings(snap, 1)[0]["sym"], "BTC")


if __name__ == "__main__":
    unittest.main()

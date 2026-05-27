from __future__ import annotations

import unittest

from terminalcrypt.dashboard import build_dashboard
from terminalcrypt.state import MarketState


class DashboardTests(unittest.TestCase):
    def test_dashboard_views_render_with_synthetic_data(self):
        state = MarketState()
        for i in range(40):
            state.update_tick("BTC", float(100 + i), 1.2, float(101 + i), float(99 + i), 1000 + i)
        snap = state.snapshot()
        build_dashboard(snap, "markets", "BTC")
        build_dashboard(snap, "detail", "BTC")
        build_dashboard(snap, "top5", "BTC")


if __name__ == "__main__":
    unittest.main()

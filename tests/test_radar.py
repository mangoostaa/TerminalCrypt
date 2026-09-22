from __future__ import annotations

import unittest

from terminalcrypt.radar import build_opportunity, scan_opportunities


def _analytics(direction="LONG", strong=True, atr=2.0, rvol=3.0):
    """Build a synthetic analytics dict biased LONG or SHORT.

    ``strong`` stacks every confirming factor; otherwise only the base signal
    is present so the two should score very differently.
    """
    if direction == "LONG":
        return {
            "history": [100.0] * 40,
            "signal": {"score": 4 if strong else 1},
            "ema": {"signal": "BULL", "cross": strong},
            "macd": {"histogram": 0.5 if strong else 0.0, "direction": "UP" if strong else "-"},
            "bb": {"zone": "LOW" if strong else "MID"},
            "momentum": {
                "squeeze": "FIRED" if strong else "-",
                "divergence": "BULL" if strong else "-",
                "roc": 3.0 if strong else 0.0,
            },
            "rsi": 55.0, "rvol": rvol, "atr": atr, "vwap": 90.0,
        }
    return {
        "history": [100.0] * 40,
        "signal": {"score": -4 if strong else -1},
        "ema": {"signal": "BEAR", "cross": strong},
        "macd": {"histogram": -0.5 if strong else 0.0, "direction": "DOWN" if strong else "-"},
        "bb": {"zone": "HIGH" if strong else "MID"},
        "momentum": {
            "squeeze": "FIRED" if strong else "-",
            "divergence": "BEAR" if strong else "-",
            "roc": -3.0 if strong else 0.0,
        },
        "rsi": 45.0, "rvol": rvol, "atr": atr, "vwap": 110.0,
    }


class _FakeCache:
    def __init__(self, mapping):
        self.mapping = mapping

    def indicators(self, sym, snapshot):
        return self.mapping[sym]


class RadarTests(unittest.TestCase):
    def test_long_opportunity_levels_ordered(self):
        opp = build_opportunity("BTC", 100.0, 0.02, _analytics("LONG", atr=2.0))
        self.assertIsNotNone(opp)
        self.assertEqual(opp.direction, "LONG")
        self.assertGreater(opp.score, 60)
        self.assertLess(opp.stop, opp.entry)
        self.assertEqual(opp.targets, sorted(opp.targets))
        self.assertTrue(all(t > opp.entry for t in opp.targets))
        # 1.5 * ATR(2%) of 100 = 3.0 stop distance
        self.assertAlmostEqual(opp.entry - opp.stop, 3.0, places=6)
        self.assertTrue(opp.reasons)

    def test_short_opportunity_levels_inverted(self):
        opp = build_opportunity("BTC", 100.0, 0.02, _analytics("SHORT", atr=2.0))
        self.assertEqual(opp.direction, "SHORT")
        self.assertGreater(opp.stop, opp.entry)
        self.assertTrue(all(t < opp.entry for t in opp.targets))

    def test_neutral_returns_none(self):
        flat = {
            "history": [100.0] * 40, "signal": {"score": 0},
            "ema": {"signal": "NEUTRAL", "cross": False}, "macd": {"histogram": 0, "direction": "-"},
            "bb": {"zone": "MID"}, "momentum": {"squeeze": "-", "divergence": "-", "roc": 0.0},
            "rsi": 50.0, "rvol": 1.0, "atr": 1.0, "vwap": None,
        }
        self.assertIsNone(build_opportunity("BTC", 100.0, 0.0, flat))

    def test_strong_setup_scores_higher_than_weak(self):
        strong = build_opportunity("BTC", 100.0, 0.0, _analytics("LONG", strong=True, rvol=3.0))
        weak = build_opportunity("BTC", 100.0, 0.0, _analytics("LONG", strong=False, rvol=1.0))
        self.assertGreater(strong.score, weak.score)

    def test_zero_price_returns_none(self):
        self.assertIsNone(build_opportunity("BTC", 0.0, 0.0, _analytics("LONG")))

    def test_scan_ranks_and_filters(self):
        snapshot = {
            "prices": {"BTC": 100.0, "ETH": 50.0, "DOGE": 0.0, "XRP": 2.0},
            "spread": {"XRP": 5.0},   # illiquid -> filtered by max_spread
            "chg24h": {"BTC": 5.0, "ETH": -4.0},
        }
        cache = _FakeCache({
            "BTC": _analytics("LONG", strong=True, rvol=3.0),
            "ETH": _analytics("SHORT", strong=False, rvol=1.6),
            "XRP": _analytics("LONG", strong=True),
        })
        results = scan_opportunities(snapshot, cache, min_score=40, limit=10)
        syms = [r["sym"] for r in results]
        self.assertIn("BTC", syms)
        self.assertNotIn("DOGE", syms)   # zero price
        self.assertNotIn("XRP", syms)    # spread too wide
        # Sorted by score descending.
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_scan_direction_filter(self):
        snapshot = {"prices": {"BTC": 100.0, "ETH": 50.0}, "spread": {}, "chg24h": {}}
        cache = _FakeCache({"BTC": _analytics("LONG"), "ETH": _analytics("SHORT")})
        longs = scan_opportunities(snapshot, cache, min_score=40, direction="LONG")
        self.assertTrue(all(o["direction"] == "LONG" for o in longs))


if __name__ == "__main__":
    unittest.main()

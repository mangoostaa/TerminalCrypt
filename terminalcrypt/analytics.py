from __future__ import annotations

from .config import COINBASE_SYMBOLS, SYMBOLS_ORDERED
from .indicators import (
    calculate_indicator_bundle,
)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class AnalyticsCache:
    def __init__(self) -> None:
        self._indicators: dict[str, tuple[int, dict]] = {}
        self._scores: dict[str, tuple[int, dict]] = {}

    def indicators(self, sym: str, s: dict) -> dict:
        tick = s.get("tick_count", {}).get(sym, 0)
        cached = self._indicators.get(sym)
        if cached and cached[0] == tick:
            return cached[1]

        tick_hist = s.get("history", {}).get(sym, [])
        tick_vol_hist = s.get("volume_history", {}).get(sym, [])
        candles_1m = s.get("candles", {}).get(60, {}).get(sym, [])
        hist = [float(c["close"]) for c in candles_1m] if len(candles_1m) >= 20 else tick_hist
        vol_hist = [float(c.get("volume", 0) or 0) for c in candles_1m] if len(candles_1m) >= 10 else tick_vol_hist
        highs = [float(c["high"]) for c in candles_1m] if len(candles_1m) >= 15 else s.get("high_history", {}).get(sym, [])
        lows = [float(c["low"]) for c in candles_1m] if len(candles_1m) >= 15 else s.get("low_history", {}).get(sym, [])
        candles = candles_1m or s.get("candle_history", {}).get(sym, [])
        current_volume = s.get("volume_delta", {}).get(sym, 0)

        bundle = calculate_indicator_bundle(hist, highs, lows, vol_hist, candles, current_volume)

        data = {
            "history": hist,
            "tick_history": tick_hist,
            "candles": candles,
            "rsi": bundle["rsi"],
            "ema": bundle["ema"],
            "averages": bundle["averages"],
            "vwap": bundle["vwap"],
            "macd": bundle["macd"],
            "bb": bundle["bb"],
            "atr": bundle["atr"],
            "rvol": bundle["rvol"],
            "momentum": bundle["momentum"],
            "signal": bundle["signal"],
        }
        self._indicators[sym] = (tick, data)
        return data

    def symbol_score(self, sym: str, s: dict) -> dict:
        tick = s.get("tick_count", {}).get(sym, 0)
        cached = self._scores.get(sym)
        if cached and cached[0] == tick:
            return cached[1]

        price = s["prices"].get(sym, 0)
        chg = s["chg24h"].get(sym, 0)
        spread = s["spread"].get(sym, 0)
        analytics = self.indicators(sym, s)
        hist = analytics["history"]
        rsi = analytics["rsi"]
        ema = analytics["ema"]
        macd = analytics["macd"]
        bb = analytics["bb"]
        atr = analytics["atr"]
        rvol = analytics["rvol"]
        momentum_extra = analytics["momentum"]
        vwap = analytics["vwap"]

        momentum = _clamp(chg / 8, -1, 1) * 22
        intraday = self.intraday_change(sym, s)
        intraday_score = _clamp(intraday / 5, -1, 1) * 10
        trend = 0
        if ema["signal"] == "BULL":
            trend += 18
        elif ema["signal"] == "BEAR":
            trend -= 18
        if ema["cross"]:
            trend += 6 if ema["signal"] == "BULL" else -6

        macd_pct = (macd["histogram"] / price * 100) if price else 0
        macd_score = _clamp(macd_pct * 22, -14, 14)
        if macd["direction"] == "UP":
            macd_score += 4
        elif macd["direction"] == "DOWN":
            macd_score -= 4

        if 45 <= rsi <= 62:
            rsi_score = 14
        elif 35 <= rsi < 45 or 62 < rsi <= 70:
            rsi_score = 6
        elif rsi < 30:
            rsi_score = -5
        else:
            rsi_score = -12

        bb_zone = bb["zone"]
        bb_score = {"LOW": 8, "MID": 5, "BELOW": 4, "HIGH": -5, "ABOVE": -10}.get(bb_zone, 0)
        squeeze_bonus = 5 if momentum_extra["squeeze"] == "FIRED" else 2 if momentum_extra["squeeze"] == "ON" else 0
        divergence_bonus = 5 if momentum_extra["divergence"] == "BULL" else -7 if momentum_extra["divergence"] == "BEAR" else 0
        vwap_bonus = 4 if vwap and price > vwap else -4 if vwap and price < vwap else 0
        liquidity = _clamp((rvol - 1) * 7, -4, 12)
        spread_penalty = _clamp(spread * 35, 0, 14) if spread else 0
        atr_penalty = _clamp(max(atr - 4, 0) * 3, 0, 12)
        data_bonus = _clamp(len(hist) / 80, 0, 1) * 8

        raw = 50 + momentum + intraday_score + trend + macd_score + rsi_score + bb_score + squeeze_bonus + divergence_bonus + vwap_bonus + liquidity + data_bonus
        score = round(_clamp(raw - spread_penalty - atr_penalty, 0, 100), 1)
        risk = "ALTO" if atr >= 4 or spread >= 0.35 else "MEDIO" if atr >= 2 or spread >= 0.15 else "BAJO"

        data = {
            "sym": sym,
            "price": price,
            "score": score,
            "chg": chg,
            "rsi": rsi,
            "ema": ema,
            "macd": macd,
            "bb": bb,
            "atr": atr,
            "rvol": rvol,
            "vwap": vwap,
            "averages": analytics["averages"],
            "momentum": momentum_extra,
            "intraday": intraday,
            "spread": spread,
            "risk": risk,
            "history": hist,
        }
        self._scores[sym] = (tick, data)
        return data

    def coinbase_score(self, sym: str, s: dict) -> dict:
        return self.symbol_score(sym, s)

    def coinbase_rankings(self, s: dict) -> list[dict]:
        symbols = sorted(set(COINBASE_SYMBOLS.values()))
        rows = [self.symbol_score(sym, s) for sym in symbols if s["prices"].get(sym, 0)]
        return sorted(rows, key=lambda row: row["score"], reverse=True)

    def score_rankings(self, s: dict, limit: int = 8) -> list[dict]:
        symbols = [sym for sym in SYMBOLS_ORDERED if s.get("prices", {}).get(sym, 0)]
        rows = [self.symbol_score(sym, s) for sym in symbols]
        return sorted(rows, key=lambda row: row["score"], reverse=True)[:limit]

    def intraday_change(self, sym: str, s: dict) -> float:
        candles = s.get("candles", {}).get(60, {}).get(sym, []) or s.get("candle_history", {}).get(sym, [])
        if candles:
            first_open = float(candles[0].get("open", 0) or 0)
            last_close = float(candles[-1].get("close", 0) or 0)
            return round((last_close - first_open) / first_open * 100, 2) if first_open else 0.0
        hist = s.get("history", {}).get(sym, [])
        return round((hist[-1] - hist[0]) / hist[0] * 100, 2) if len(hist) >= 2 and hist[0] else 0.0

    def intraday_rankings(self, s: dict, limit: int = 8) -> list[dict]:
        rows = []
        for sym, price in s.get("prices", {}).items():
            if price:
                rows.append({
                    "sym": sym,
                    "price": price,
                    "intraday": self.intraday_change(sym, s),
                    "chg": s.get("chg24h", {}).get(sym, 0),
                })
        return sorted(rows, key=lambda row: row["intraday"], reverse=True)[:limit]

    def volume_rankings(self, s: dict, limit: int = 8) -> list[dict]:
        rows = []
        for sym, price in s.get("prices", {}).items():
            if price:
                analytics = self.indicators(sym, s)
                rows.append({
                    "sym": sym,
                    "price": price,
                    "volume": s.get("vol24", {}).get(sym, 0),
                    "rvol": analytics["rvol"],
                })
        return sorted(rows, key=lambda row: (row["rvol"], row["volume"]), reverse=True)[:limit]


analytics_cache = AnalyticsCache()

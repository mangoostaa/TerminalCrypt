from __future__ import annotations

from .config import COINBASE_SYMBOLS
from .indicators import (
    calculate_atr,
    calculate_bollinger,
    calculate_ema_cross,
    calculate_macd,
    calculate_rsi,
    calculate_signal,
    relative_volume,
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

        hist = s.get("history", {}).get(sym, [])
        vol_hist = s.get("volume_history", {}).get(sym, [])
        highs = s.get("high_history", {}).get(sym, [])
        lows = s.get("low_history", {}).get(sym, [])
        vol24 = s.get("vol24", {}).get(sym, 0)

        rsi = calculate_rsi(hist)
        ema = calculate_ema_cross(hist)
        macd = calculate_macd(hist)
        bb = calculate_bollinger(hist)
        atr = calculate_atr(highs, lows, hist)
        rvol = relative_volume(vol_hist, vol24)
        signal = calculate_signal(rsi, ema, macd, bb)

        data = {
            "history": hist,
            "rsi": rsi,
            "ema": ema,
            "macd": macd,
            "bb": bb,
            "atr": atr,
            "rvol": rvol,
            "signal": signal,
        }
        self._indicators[sym] = (tick, data)
        return data

    def coinbase_score(self, sym: str, s: dict) -> dict:
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

        momentum = _clamp(chg / 8, -1, 1) * 22
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
        liquidity = _clamp((rvol - 1) * 7, -4, 12)
        spread_penalty = _clamp(spread * 35, 0, 14) if spread else 0
        atr_penalty = _clamp(max(atr - 4, 0) * 3, 0, 12)
        data_bonus = _clamp(len(hist) / 80, 0, 1) * 8

        raw = 50 + momentum + trend + macd_score + rsi_score + bb_score + liquidity + data_bonus
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
            "spread": spread,
            "risk": risk,
            "history": hist,
        }
        self._scores[sym] = (tick, data)
        return data

    def coinbase_rankings(self, s: dict) -> list[dict]:
        symbols = sorted(set(COINBASE_SYMBOLS.values()))
        rows = [self.coinbase_score(sym, s) for sym in symbols if s["prices"].get(sym, 0)]
        return sorted(rows, key=lambda row: row["score"], reverse=True)


analytics_cache = AnalyticsCache()

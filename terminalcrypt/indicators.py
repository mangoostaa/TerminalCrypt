from __future__ import annotations

_BACKEND = "python"


def calculate_rsi(prices: list, period: int = 14) -> float:
    if len(prices) < period + 1:
        return 50.0
    gains = [max(prices[i] - prices[i - 1], 0) for i in range(1, len(prices))]
    losses = [abs(min(prices[i] - prices[i - 1], 0)) for i in range(1, len(prices))]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period if sum(losses[-period:]) > 0 else 0.0001
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def calculate_ema(prices: list, period: int) -> list:
    if len(prices) < period:
        return [None] * len(prices)
    k = 2 / (period + 1)
    result = [None] * (period - 1)
    sma = sum(prices[:period]) / period
    result.append(sma)
    for p in prices[period:]:
        result.append(p * k + result[-1] * (1 - k))
    return result


def calculate_ema_cross(prices: list, fast: int = 9, slow: int = 21) -> dict:
    if len(prices) < slow + 1:
        return {"signal": "NEUTRAL", "ema_fast": None, "ema_slow": None, "cross": False}
    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)
    pairs = [(f, s) for f, s in zip(fast_ema, slow_ema) if f is not None and s is not None]
    if len(pairs) < 2:
        return {"signal": "NEUTRAL", "ema_fast": None, "ema_slow": None, "cross": False}
    cur_f, cur_s = pairs[-1]
    prev_f, prev_s = pairs[-2]
    signal = "BULL" if cur_f > cur_s else "BEAR"
    cross = (prev_f <= prev_s and cur_f > cur_s) or (prev_f >= prev_s and cur_f < cur_s)
    return {"signal": signal, "ema_fast": cur_f, "ema_slow": cur_s, "cross": cross}


def calculate_macd(prices: list, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    if len(prices) < slow + signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "-"}
    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema) if f is not None and s is not None]
    if len(macd_line) < signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "-"}
    sig_line = calculate_ema(macd_line, signal)
    sig_vals = [v for v in sig_line if v is not None]
    if not sig_vals:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "-"}
    ml = macd_line[-1]
    sl = sig_vals[-1]
    hist = ml - sl
    hist_prev = (macd_line[-2] - sig_vals[-2]) if len(macd_line) >= 2 and len(sig_vals) >= 2 else hist
    direction = "UP" if hist > hist_prev else "DOWN"
    return {
        "macd_line": round(ml, 6),
        "signal_line": round(sl, 6),
        "histogram": round(hist, 6),
        "direction": direction,
    }


def calculate_bollinger(prices: list, period: int = 20, std_mult: float = 2.0) -> dict:
    if len(prices) < period:
        return {"upper": 0, "middle": 0, "lower": 0, "pct_b": 0.5, "zone": "MID", "bandwidth": 0}
    sample = prices[-period:]
    mid = sum(sample) / period
    variance = sum((p - mid) ** 2 for p in sample) / period
    std = variance ** 0.5
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    price = prices[-1]
    band_range = upper - lower or 0.0001
    pct_b = (price - lower) / band_range
    bandwidth = (upper - lower) / mid * 100 if mid else 0
    if price > upper:
        zone = "ABOVE"
    elif pct_b >= 0.8:
        zone = "HIGH"
    elif pct_b <= 0.2:
        zone = "LOW"
    elif price < lower:
        zone = "BELOW"
    else:
        zone = "MID"
    return {
        "upper": round(upper, 6),
        "middle": round(mid, 6),
        "lower": round(lower, 6),
        "pct_b": round(pct_b, 3),
        "zone": zone,
        "bandwidth": round(bandwidth, 2),
    }


def calculate_atr(highs: list, lows: list, closes: list, period: int = 14) -> float:
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0
    trs = []
    for i in range(1, n):
        hl = highs[i] - lows[i]
        hcp = abs(highs[i] - closes[i - 1])
        lcp = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hcp, lcp))
    if len(trs) < period:
        return 0.0
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    price = closes[-1]
    return round((atr / price * 100), 3) if price else 0.0


def calculate_signal(rsi: float, ema_cross: dict, macd: dict, bb: dict) -> dict:
    score = 0
    if rsi < 30:
        score += 1
    elif rsi > 70:
        score -= 1
    if ema_cross.get("signal") == "BULL":
        score += 1
    elif ema_cross.get("signal") == "BEAR":
        score -= 1
    if ema_cross.get("cross"):
        score += 1 if ema_cross["signal"] == "BULL" else -1
    hist = macd.get("histogram", 0)
    direction = macd.get("direction", "-")
    if hist > 0 and direction == "UP":
        score += 1
    elif hist < 0 and direction == "DOWN":
        score -= 1
    zone = bb.get("zone", "MID")
    if zone in ("LOW", "BELOW"):
        score += 1
    elif zone in ("HIGH", "ABOVE"):
        score -= 1
    if score >= 3:
        sig, col, icon = "STR LONG", "bold bright_green", "OO"
    elif score >= 1:
        sig, col, icon = "LONG", "green", "Oo"
    elif score <= -3:
        sig, col, icon = "STR SHORT", "bold bright_red", "OO"
    elif score <= -1:
        sig, col, icon = "SHORT", "red", "Oo"
    else:
        sig, col, icon = "NEUTRAL", "yellow", "oo"
    return {"score": score, "signal": sig, "color": col, "icon": icon}


def relative_volume(vol_history: list, current_vol: float) -> float:
    if len(vol_history) < 10 or current_vol <= 0:
        return 1.0
    sample = list(vol_history)[-20:]
    avg_vol = sum(sample) / len(sample)
    return round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0


try:
    from ._cython.indicators_cy import (
        calculate_rsi,
        calculate_ema,
        calculate_ema_cross,
        calculate_macd,
        calculate_bollinger,
        calculate_atr,
        calculate_signal,
        relative_volume,
    )

    _BACKEND = "cython"
except Exception:
    pass

try:
    from ._rust import (
        calculate_rsi,
        calculate_ema,
        calculate_ema_cross,
        calculate_macd,
        calculate_bollinger,
        calculate_atr,
        calculate_signal,
        relative_volume,
    )

    _BACKEND = "rust"
except Exception:
    pass

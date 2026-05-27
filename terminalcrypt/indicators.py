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


def calculate_sma(prices: list, period: int) -> list:
    if period <= 0:
        return [None] * len(prices)
    result = []
    for i in range(len(prices)):
        if i + 1 < period:
            result.append(None)
        else:
            sample = prices[i + 1 - period : i + 1]
            result.append(sum(sample) / period)
    return result


def latest_sma(prices: list, period: int) -> float | None:
    vals = [v for v in calculate_sma(prices, period) if v is not None]
    return round(vals[-1], 6) if vals else None


def latest_ema(prices: list, period: int) -> float | None:
    vals = [v for v in calculate_ema(prices, period) if v is not None]
    return round(vals[-1], 6) if vals else None


def calculate_vwap(candles: list, period: int = 20) -> float | None:
    if not candles:
        return None
    sample = candles[-period:] if period else candles
    pv_sum = 0.0
    vol_sum = 0.0
    for candle in sample:
        high = float(candle.get("high", 0) or 0)
        low = float(candle.get("low", 0) or 0)
        close = float(candle.get("close", 0) or 0)
        volume = float(candle.get("volume", 0) or 0)
        typical = (high + low + close) / 3 if high and low and close else close
        pv_sum += typical * volume
        vol_sum += volume
    return round(pv_sum / vol_sum, 6) if vol_sum > 0 else None


def calculate_moving_averages(prices: list, sma_periods: tuple = (20, 50), ema_periods: tuple = (9, 21, 50)) -> dict:
    return {
        "sma": {period: latest_sma(prices, period) for period in sma_periods},
        "ema": {period: latest_ema(prices, period) for period in ema_periods},
    }


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


def bollinger_bandwidth_series(prices: list, period: int = 20, std_mult: float = 2.0) -> list:
    values = []
    for i in range(period, len(prices) + 1):
        sample = prices[i - period : i]
        mid = sum(sample) / period
        variance = sum((p - mid) ** 2 for p in sample) / period
        std = variance ** 0.5
        values.append(((std_mult * 2 * std) / mid * 100) if mid else 0)
    return values


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


def calculate_momentum(prices: list, rsi_values: list | None = None, period: int = 10) -> dict:
    if len(prices) <= period:
        return {"roc": 0.0, "state": "NEUTRAL", "divergence": "-", "squeeze": "-"}
    prev = prices[-period - 1]
    roc = ((prices[-1] - prev) / prev * 100) if prev else 0.0
    if roc >= 2:
        state = "BULL"
    elif roc <= -2:
        state = "BEAR"
    else:
        state = "NEUTRAL"

    divergence = "-"
    if len(prices) >= 30:
        left = prices[-30:-15]
        right = prices[-15:]
        left_high = max(left)
        right_high = max(right)
        left_low = min(left)
        right_low = min(right)
        if rsi_values and len(rsi_values) >= 30:
            left_rsi = max(rsi_values[-30:-15])
            right_rsi = max(rsi_values[-15:])
            left_rsi_low = min(rsi_values[-30:-15])
            right_rsi_low = min(rsi_values[-15:])
            if right_high > left_high and right_rsi < left_rsi:
                divergence = "BEAR"
            elif right_low < left_low and right_rsi_low > left_rsi_low:
                divergence = "BULL"

    widths = bollinger_bandwidth_series(prices)
    squeeze = "-"
    if len(widths) >= 20:
        recent = widths[-1]
        baseline = sorted(widths[-20:])
        threshold = baseline[max(0, int(len(baseline) * 0.2) - 1)]
        if recent <= threshold:
            squeeze = "ON"
        elif len(widths) >= 2 and widths[-2] <= threshold < recent:
            squeeze = "FIRED"

    return {
        "roc": round(roc, 2),
        "state": state,
        "divergence": divergence,
        "squeeze": squeeze,
    }


def _calculate_signal_extended(rsi: float, ema_cross: dict, macd: dict, bb: dict, momentum: dict | None = None) -> dict:
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
    if momentum:
        if momentum.get("state") == "BULL":
            score += 1
        elif momentum.get("state") == "BEAR":
            score -= 1
        if momentum.get("divergence") == "BULL":
            score += 1
        elif momentum.get("divergence") == "BEAR":
            score -= 1
        if momentum.get("squeeze") == "FIRED":
            score += 1 if macd.get("histogram", 0) >= 0 else -1
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


calculate_signal = _calculate_signal_extended


def relative_volume(vol_history: list, current_vol: float) -> float:
    if len(vol_history) < 10 or current_vol <= 0:
        return 1.0
    sample = list(vol_history)[-20:]
    avg_vol = sum(sample) / len(sample)
    return round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0


def calculate_rsi_series(prices: list, period: int = 14) -> list:
    if period <= 0:
        return [50.0] * len(prices)
    values = [50.0] * min(len(prices), period)
    gains: list[float] = []
    losses: list[float] = []
    gain_sum = 0.0
    loss_sum = 0.0
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gain = max(diff, 0)
        loss = abs(min(diff, 0))
        gains.append(gain)
        losses.append(loss)
        gain_sum += gain
        loss_sum += loss
        if len(gains) > period:
            gain_sum -= gains[-period - 1]
            loss_sum -= losses[-period - 1]
        if len(gains) >= period:
            avg_gain = gain_sum / period
            avg_loss = loss_sum / period if loss_sum > 0 else 0.0001
            rs = avg_gain / avg_loss
            values.append(round(100 - (100 / (1 + rs)), 1))
    return values


def _calculate_indicator_bundle_python(
    hist: list,
    highs: list,
    lows: list,
    vol_hist: list,
    candles: list,
    current_volume: float,
) -> dict:
    rsi = calculate_rsi(hist)
    rsi_series = calculate_rsi_series(hist)
    ema = calculate_ema_cross(hist)
    macd = calculate_macd(hist)
    bb = calculate_bollinger(hist)
    atr = calculate_atr(highs, lows, hist)
    rvol = relative_volume(vol_hist, current_volume)
    vwap = calculate_vwap(candles)
    averages = calculate_moving_averages(hist)
    momentum = calculate_momentum(hist, rsi_series)
    signal = calculate_signal(rsi, ema, macd, bb, momentum)
    return {
        "rsi": rsi,
        "ema": ema,
        "averages": averages,
        "vwap": vwap,
        "macd": macd,
        "bb": bb,
        "atr": atr,
        "rvol": rvol,
        "momentum": momentum,
        "signal": signal,
    }


_calculate_indicator_bundle_native = None


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
    try:
        from ._rust import calculate_indicator_bundle as _calculate_indicator_bundle_native
    except Exception:
        pass

    _BACKEND = "rust"
except Exception:
    pass

calculate_signal = _calculate_signal_extended


def calculate_indicator_bundle(
    hist: list,
    highs: list,
    lows: list,
    vol_hist: list,
    candles: list,
    current_volume: float,
) -> dict:
    if _calculate_indicator_bundle_native is not None:
        try:
            data = _calculate_indicator_bundle_native(hist, highs, lows, vol_hist, current_volume)
            data["vwap"] = calculate_vwap(candles)
            return data
        except Exception:
            pass
    return _calculate_indicator_bundle_python(hist, highs, lows, vol_hist, candles, current_volume)

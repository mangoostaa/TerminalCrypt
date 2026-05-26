# cython: language_level=3
from cpython cimport PyFloat_FromDouble
from libc.math cimport sqrt
from libcpp cimport bool

def calculate_rsi(prices, int period=14):
    cdef Py_ssize_t n = len(prices)
    if n < period + 1:
        return 50.0
    cdef double gains = 0.0
    cdef double losses = 0.0
    cdef Py_ssize_t i
    cdef double diff, cur, prev
    for i in range(1, n):
        cur = float(prices[i])
        prev = float(prices[i - 1])
        diff = cur - prev
        if diff > 0:
            gains += diff if i >= n - period else 0.0
        else:
            losses += (-diff) if i >= n - period else 0.0

    # compute average over last `period` deltas
    # fallback simple approach: compute gains/losses over last period
    gains = 0.0
    losses = 0.0
    for i in range(n - period, n):
        diff = float(prices[i]) - float(prices[i - 1])
        if diff > 0:
            gains += diff
        else:
            losses += -diff

    cdef double avg_gain = gains / period
    cdef double avg_loss = losses / period if losses > 0 else 0.0001
    cdef double rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 1)


def calculate_ema(prices, int period):
    cdef Py_ssize_t n = len(prices)
    if n < period:
        return [None] * n
    cdef double k = 2.0 / (period + 1)
    result = [None] * (period - 1)
    cdef double sma = 0.0
    cdef Py_ssize_t i
    for i in range(period):
        sma += float(prices[i])
    sma = sma / period
    result.append(sma)
    cdef double prev = sma
    for i in range(period, n):
        prev = float(prices[i]) * k + prev * (1 - k)
        result.append(prev)
    return result


def calculate_ema_cross(prices, int fast=9, int slow=21):
    if len(prices) < slow + 1:
        return {"signal": "NEUTRAL", "ema_fast": None, "ema_slow": None, "cross": False}
    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)
    pairs = []
    for f, s in zip(fast_ema, slow_ema):
        if f is not None and s is not None:
            pairs.append((f, s))
    if len(pairs) < 2:
        return {"signal": "NEUTRAL", "ema_fast": None, "ema_slow": None, "cross": False}
    cur_f, cur_s = pairs[-1]
    prev_f, prev_s = pairs[-2]
    signal = "BULL" if cur_f > cur_s else "BEAR"
    cross = (prev_f <= prev_s and cur_f > cur_s) or (prev_f >= prev_s and cur_f < cur_s)
    return {"signal": signal, "ema_fast": cur_f, "ema_slow": cur_s, "cross": cross}


def calculate_macd(prices, int fast=12, int slow=26, int signal=9):
    if len(prices) < slow + signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "─"}
    fast_ema = calculate_ema(prices, fast)
    slow_ema = calculate_ema(prices, slow)
    macd_line = []
    for f, s in zip(fast_ema, slow_ema):
        if f is not None and s is not None:
            macd_line.append(f - s)
    if len(macd_line) < signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "─"}
    sig_line = calculate_ema(macd_line, signal)
    sig_vals = [v for v in sig_line if v is not None]
    if not sig_vals:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "direction": "─"}
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


def calculate_bollinger(prices, int period=20, double std_mult=2.0):
    if len(prices) < period:
        return {"upper": 0, "middle": 0, "lower": 0, "pct_b": 0.5, "zone": "MID", "bandwidth": 0}
    sample = prices[-period:]
    cdef double mid = 0.0
    cdef Py_ssize_t i
    for i in range(period):
        mid += float(sample[i])
    mid = mid / period
    cdef double variance = 0.0
    for i in range(period):
        variance += (float(sample[i]) - mid) ** 2
    variance = variance / period
    cdef double std = sqrt(variance)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    price = float(prices[-1])
    band_range = upper - lower if (upper - lower) != 0 else 0.0001
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
    return {"upper": round(upper, 6), "middle": round(mid, 6), "lower": round(lower, 6), "pct_b": round(pct_b, 3), "zone": zone, "bandwidth": round(bandwidth, 2)}


def calculate_atr(highs, lows, closes, int period=14):
    n = min(len(highs), len(lows), len(closes))
    if n < period + 1:
        return 0.0
    trs = []
    cdef Py_ssize_t i
    for i in range(1, n):
        hl = float(highs[i]) - float(lows[i])
        hcp = abs(float(highs[i]) - float(closes[i - 1]))
        lcp = abs(float(lows[i]) - float(closes[i - 1]))
        trs.append(max(hl, hcp, lcp))
    if len(trs) < period:
        return 0.0
    cdef double atr = 0.0
    for i in range(period):
        atr += trs[i]
    atr = atr / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    price = float(closes[-1])
    return round((atr / price * 100), 3) if price else 0.0


def calculate_signal(rsi, ema_cross, macd, bb):
    # simple passthrough to Python-friendly dict logic
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
        score += 1 if ema_cross.get("signal") == "BULL" else -1
    hist = macd.get("histogram", 0)
    direction = macd.get("direction", "─")
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
        sig, col, icon = "STR LONG", "bold bright_green", "●●"
    elif score >= 1:
        sig, col, icon = "LONG", "green", "●○"
    elif score <= -3:
        sig, col, icon = "STR SHORT", "bold bright_red", "●●"
    elif score <= -1:
        sig, col, icon = "SHORT", "red", "●○"
    else:
        sig, col, icon = "NEUTRAL", "yellow", "○○"
    return {"score": score, "signal": sig, "color": col, "icon": icon}


def relative_volume(vol_history, current_vol):
    if len(vol_history) < 10 or current_vol <= 0:
        return 1.0
    # average last up to 20
    sample = vol_history[-20:]
    s = 0.0
    cdef Py_ssize_t i
    for i in range(len(sample)):
        s += float(sample[i])
    avg_vol = s / len(sample) if len(sample) > 0 else 0.0
    return round(current_vol / avg_vol, 2) if avg_vol > 0 else 1.0

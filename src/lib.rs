use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use rayon::join;

#[cfg(target_arch = "x86")]
use std::arch::x86::{
    __m256d, _mm256_add_pd, _mm256_loadu_pd, _mm256_mul_pd, _mm256_set1_pd, _mm256_setzero_pd,
    _mm256_storeu_pd, _mm256_sub_pd,
};
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::{
    __m256d, _mm256_add_pd, _mm256_loadu_pd, _mm256_mul_pd, _mm256_set1_pd, _mm256_setzero_pd,
    _mm256_storeu_pd, _mm256_sub_pd,
};

fn floats(values: &Bound<'_, PyAny>) -> PyResult<Vec<f64>> {
    values.extract::<Vec<f64>>()
}

fn round_to(value: f64, decimals: i32) -> f64 {
    let scale = 10_f64.powi(decimals);
    (value * scale).round() / scale
}

fn sum_f64(values: &[f64]) -> f64 {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    {
        if std::is_x86_feature_detected!("avx2") {
            return unsafe { sum_f64_avx2(values) };
        }
    }
    values.iter().sum()
}

fn sum_sq_diff_f64(values: &[f64], center: f64) -> f64 {
    #[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
    {
        if std::is_x86_feature_detected!("avx2") {
            return unsafe { sum_sq_diff_f64_avx2(values, center) };
        }
    }
    values.iter().map(|v| (v - center).powi(2)).sum()
}

#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
#[target_feature(enable = "avx,avx2")]
unsafe fn sum_f64_avx2(values: &[f64]) -> f64 {
    let mut i = 0;
    let mut acc: __m256d = _mm256_setzero_pd();
    while i + 4 <= values.len() {
        let lane = unsafe { _mm256_loadu_pd(values.as_ptr().add(i)) };
        acc = _mm256_add_pd(acc, lane);
        i += 4;
    }

    let mut tmp = [0.0_f64; 4];
    unsafe { _mm256_storeu_pd(tmp.as_mut_ptr(), acc) };
    let mut total = tmp.iter().sum::<f64>();
    for value in &values[i..] {
        total += *value;
    }
    total
}

#[cfg(any(target_arch = "x86", target_arch = "x86_64"))]
#[target_feature(enable = "avx,avx2")]
unsafe fn sum_sq_diff_f64_avx2(values: &[f64], center: f64) -> f64 {
    let mut i = 0;
    let mut acc: __m256d = _mm256_setzero_pd();
    let center_lane = _mm256_set1_pd(center);
    while i + 4 <= values.len() {
        let lane = unsafe { _mm256_loadu_pd(values.as_ptr().add(i)) };
        let diff = _mm256_sub_pd(lane, center_lane);
        acc = _mm256_add_pd(acc, _mm256_mul_pd(diff, diff));
        i += 4;
    }

    let mut tmp = [0.0_f64; 4];
    unsafe { _mm256_storeu_pd(tmp.as_mut_ptr(), acc) };
    let mut total = tmp.iter().sum::<f64>();
    for value in &values[i..] {
        let diff = *value - center;
        total += diff * diff;
    }
    total
}

fn latest_sma_value(prices: &[f64], period: usize) -> Option<f64> {
    if period == 0 || prices.len() < period {
        return None;
    }
    Some(round_to(
        sum_f64(&prices[prices.len() - period..]) / period as f64,
        6,
    ))
}

fn latest_ema_value(prices: &[f64], period: usize) -> Option<f64> {
    ema_last_two(prices, period).1.map(|v| round_to(v, 6))
}

fn ema_values(prices: &[f64], period: usize) -> Vec<Option<f64>> {
    if period == 0 || prices.len() < period {
        return vec![None; prices.len()];
    }

    let k = 2.0 / (period as f64 + 1.0);
    let mut result = vec![None; period - 1];
    let mut prev = sum_f64(&prices[..period]) / period as f64;
    result.push(Some(prev));

    for price in &prices[period..] {
        prev = price * k + prev * (1.0 - k);
        result.push(Some(prev));
    }

    result
}

fn rsi_value(prices: &[f64], period: usize) -> f64 {
    if prices.len() < period + 1 || period == 0 {
        return 50.0;
    }

    let start = prices.len() - period;
    let mut gains = 0.0;
    let mut losses = 0.0;

    for i in start..prices.len() {
        let diff = prices[i] - prices[i - 1];
        if diff > 0.0 {
            gains += diff;
        } else {
            losses += -diff;
        }
    }

    let avg_gain = gains / period as f64;
    let avg_loss = if losses > 0.0 {
        losses / period as f64
    } else {
        0.0001
    };
    let rs = avg_gain / avg_loss;
    round_to(100.0 - (100.0 / (1.0 + rs)), 1)
}

struct EmaCrossRaw {
    signal: &'static str,
    ema_fast: Option<f64>,
    ema_slow: Option<f64>,
    cross: bool,
}

struct MacdRaw {
    macd_line: f64,
    signal_line: f64,
    histogram: f64,
    direction: &'static str,
}

struct BollingerRaw {
    upper: f64,
    middle: f64,
    lower: f64,
    pct_b: f64,
    zone: &'static str,
    bandwidth: f64,
}

struct MomentumRaw {
    roc: f64,
    state: &'static str,
    divergence: &'static str,
    squeeze: &'static str,
}

fn ema_last_two(prices: &[f64], period: usize) -> (Option<f64>, Option<f64>) {
    if period == 0 || prices.len() < period {
        return (None, None);
    }
    let k = 2.0 / (period as f64 + 1.0);
    let mut current = sum_f64(&prices[..period]) / period as f64;
    let mut previous = None;
    for price in &prices[period..] {
        previous = Some(current);
        current = price * k + current * (1.0 - k);
    }
    (previous, Some(current))
}

fn ema_cross_raw(prices: &[f64]) -> EmaCrossRaw {
    if prices.len() < 22 {
        return EmaCrossRaw {
            signal: "NEUTRAL",
            ema_fast: None,
            ema_slow: None,
            cross: false,
        };
    }
    let (prev_f, cur_f) = ema_last_two(prices, 9);
    let (prev_s, cur_s) = ema_last_two(prices, 21);
    match (prev_f, cur_f, prev_s, cur_s) {
        (Some(prev_f), Some(cur_f), Some(prev_s), Some(cur_s)) => {
            let signal = if cur_f > cur_s { "BULL" } else { "BEAR" };
            let cross = (prev_f <= prev_s && cur_f > cur_s) || (prev_f >= prev_s && cur_f < cur_s);
            EmaCrossRaw {
                signal,
                ema_fast: Some(cur_f),
                ema_slow: Some(cur_s),
                cross,
            }
        }
        _ => EmaCrossRaw {
            signal: "NEUTRAL",
            ema_fast: None,
            ema_slow: None,
            cross: false,
        },
    }
}

fn macd_raw(prices: &[f64]) -> MacdRaw {
    if prices.len() < 35 {
        return MacdRaw {
            macd_line: 0.0,
            signal_line: 0.0,
            histogram: 0.0,
            direction: "-",
        };
    }

    let fast = 12;
    let slow = 26;
    let signal = 9;
    let fast_k = 2.0 / (fast as f64 + 1.0);
    let slow_k = 2.0 / (slow as f64 + 1.0);
    let signal_k = 2.0 / (signal as f64 + 1.0);
    let mut fast_ema = sum_f64(&prices[..fast]) / fast as f64;
    let mut slow_ema = sum_f64(&prices[..slow]) / slow as f64;
    let mut macd_count = 0_usize;
    let mut signal_seed = 0.0;
    let mut signal_ema = 0.0;
    let mut prev_hist = 0.0;
    let mut hist = 0.0;
    let mut last_macd = 0.0;

    for (i, price) in prices.iter().enumerate() {
        if i >= fast {
            fast_ema = price * fast_k + fast_ema * (1.0 - fast_k);
        }
        if i >= slow {
            slow_ema = price * slow_k + slow_ema * (1.0 - slow_k);
            last_macd = fast_ema - slow_ema;
            macd_count += 1;
            if macd_count <= signal {
                signal_seed += last_macd;
                if macd_count == signal {
                    signal_ema = signal_seed / signal as f64;
                    hist = last_macd - signal_ema;
                    prev_hist = hist;
                }
                continue;
            }
            signal_ema = last_macd * signal_k + signal_ema * (1.0 - signal_k);
            prev_hist = hist;
            hist = last_macd - signal_ema;
        }
    }

    if macd_count < signal {
        return MacdRaw {
            macd_line: 0.0,
            signal_line: 0.0,
            histogram: 0.0,
            direction: "-",
        };
    }

    MacdRaw {
        macd_line: round_to(last_macd, 6),
        signal_line: round_to(signal_ema, 6),
        histogram: round_to(hist, 6),
        direction: if hist > prev_hist { "UP" } else { "DOWN" },
    }
}

fn bollinger_raw(prices: &[f64]) -> BollingerRaw {
    if prices.len() < 20 {
        return BollingerRaw {
            upper: 0.0,
            middle: 0.0,
            lower: 0.0,
            pct_b: 0.5,
            zone: "MID",
            bandwidth: 0.0,
        };
    }
    let sample = &prices[prices.len() - 20..];
    let mid = sum_f64(sample) / 20.0;
    let variance = sum_sq_diff_f64(sample, mid) / 20.0;
    let std = variance.sqrt();
    let upper = mid + 2.0 * std;
    let lower = mid - 2.0 * std;
    let price = *prices.last().unwrap();
    let band_range = if upper - lower != 0.0 {
        upper - lower
    } else {
        0.0001
    };
    let pct_b = (price - lower) / band_range;
    let bandwidth = if mid != 0.0 {
        (upper - lower) / mid * 100.0
    } else {
        0.0
    };
    let zone = if price > upper {
        "ABOVE"
    } else if pct_b >= 0.8 {
        "HIGH"
    } else if pct_b <= 0.2 {
        "LOW"
    } else if price < lower {
        "BELOW"
    } else {
        "MID"
    };
    BollingerRaw {
        upper: round_to(upper, 6),
        middle: round_to(mid, 6),
        lower: round_to(lower, 6),
        pct_b: round_to(pct_b, 3),
        zone,
        bandwidth: round_to(bandwidth, 2),
    }
}

fn atr_raw(highs: &[f64], lows: &[f64], closes: &[f64]) -> f64 {
    let n = highs.len().min(lows.len()).min(closes.len());
    if n < 15 {
        return 0.0;
    }
    let mut atr = 0.0;
    for i in 1..=14 {
        let hl = highs[i] - lows[i];
        let hcp = (highs[i] - closes[i - 1]).abs();
        let lcp = (lows[i] - closes[i - 1]).abs();
        atr += hl.max(hcp).max(lcp);
    }
    atr /= 14.0;
    for i in 15..n {
        let hl = highs[i] - lows[i];
        let hcp = (highs[i] - closes[i - 1]).abs();
        let lcp = (lows[i] - closes[i - 1]).abs();
        atr = (atr * 13.0 + hl.max(hcp).max(lcp)) / 14.0;
    }
    let price = closes[closes.len() - 1];
    if price != 0.0 {
        round_to(atr / price * 100.0, 3)
    } else {
        0.0
    }
}

fn relative_volume_raw(vol_history: &[f64], current_vol: f64) -> f64 {
    if vol_history.len() < 10 || current_vol <= 0.0 {
        return 1.0;
    }
    let start = vol_history.len().saturating_sub(20);
    let sample = &vol_history[start..];
    let avg_vol = sum_f64(sample) / sample.len() as f64;
    if avg_vol > 0.0 {
        round_to(current_vol / avg_vol, 2)
    } else {
        1.0
    }
}

fn rsi_range_extremes(prices: &[f64], start: usize, end: usize) -> (f64, f64) {
    let mut high = f64::NEG_INFINITY;
    let mut low = f64::INFINITY;
    for idx in start..end {
        let value = rsi_value(&prices[..=idx], 14);
        high = high.max(value);
        low = low.min(value);
    }
    (high, low)
}

fn squeeze_state(prices: &[f64]) -> &'static str {
    if prices.len() < 39 {
        return "-";
    }
    let mut widths = [0.0_f64; 20];
    let first_window_end = prices.len() - 19;
    for (slot, end) in (first_window_end..=prices.len()).enumerate() {
        let sample = &prices[end - 20..end];
        let mid = sum_f64(sample) / 20.0;
        let variance = sum_sq_diff_f64(sample, mid) / 20.0;
        let std = variance.sqrt();
        widths[slot] = if mid != 0.0 {
            (4.0 * std) / mid * 100.0
        } else {
            0.0
        };
    }
    let recent = widths[19];
    let previous = widths[18];
    let mut baseline = widths;
    baseline.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
    let threshold = baseline[3];
    if recent <= threshold {
        "ON"
    } else if previous <= threshold && threshold < recent {
        "FIRED"
    } else {
        "-"
    }
}

fn momentum_raw(prices: &[f64]) -> MomentumRaw {
    if prices.len() <= 10 {
        return MomentumRaw {
            roc: 0.0,
            state: "NEUTRAL",
            divergence: "-",
            squeeze: "-",
        };
    }
    let prev = prices[prices.len() - 11];
    let roc = if prev != 0.0 {
        (prices[prices.len() - 1] - prev) / prev * 100.0
    } else {
        0.0
    };
    let state = if roc >= 2.0 {
        "BULL"
    } else if roc <= -2.0 {
        "BEAR"
    } else {
        "NEUTRAL"
    };
    let mut divergence = "-";
    if prices.len() >= 30 {
        let left = &prices[prices.len() - 30..prices.len() - 15];
        let right = &prices[prices.len() - 15..];
        let left_high = left.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let right_high = right.iter().copied().fold(f64::NEG_INFINITY, f64::max);
        let left_low = left.iter().copied().fold(f64::INFINITY, f64::min);
        let right_low = right.iter().copied().fold(f64::INFINITY, f64::min);
        let (left_rsi, left_rsi_low) =
            rsi_range_extremes(prices, prices.len() - 30, prices.len() - 15);
        let (right_rsi, right_rsi_low) =
            rsi_range_extremes(prices, prices.len() - 15, prices.len());
        if right_high > left_high && right_rsi < left_rsi {
            divergence = "BEAR";
        } else if right_low < left_low && right_rsi_low > left_rsi_low {
            divergence = "BULL";
        }
    }
    MomentumRaw {
        roc: round_to(roc, 2),
        state,
        divergence,
        squeeze: squeeze_state(prices),
    }
}

#[pyfunction]
#[pyo3(signature = (prices, period = 14))]
fn calculate_rsi(prices: &Bound<'_, PyAny>, period: usize) -> PyResult<f64> {
    let prices = floats(prices)?;
    Ok(rsi_value(&prices, period))
}

#[pyfunction]
fn calculate_ema(py: Python<'_>, prices: &Bound<'_, PyAny>, period: usize) -> PyResult<Py<PyAny>> {
    let prices = floats(prices)?;
    let result = ema_values(&prices, period);
    let out = PyList::empty(py);

    for value in result {
        match value {
            Some(v) => out.append(v)?,
            None => out.append(py.None())?,
        }
    }

    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (prices, fast = 9, slow = 21))]
fn calculate_ema_cross(
    py: Python<'_>,
    prices: &Bound<'_, PyAny>,
    fast: usize,
    slow: usize,
) -> PyResult<Py<PyAny>> {
    let prices = floats(prices)?;
    let out = PyDict::new(py);

    if fast == 9 && slow == 21 {
        let raw = ema_cross_raw(&prices);
        out.set_item("signal", raw.signal)?;
        match raw.ema_fast {
            Some(v) => out.set_item("ema_fast", v)?,
            None => out.set_item("ema_fast", py.None())?,
        }
        match raw.ema_slow {
            Some(v) => out.set_item("ema_slow", v)?,
            None => out.set_item("ema_slow", py.None())?,
        }
        out.set_item("cross", raw.cross)?;
        return Ok(out.into());
    }

    if prices.len() < slow + 1 || fast == 0 || slow == 0 {
        out.set_item("signal", "NEUTRAL")?;
        out.set_item("ema_fast", py.None())?;
        out.set_item("ema_slow", py.None())?;
        out.set_item("cross", false)?;
        return Ok(out.into());
    }

    let fast_ema = ema_values(&prices, fast);
    let slow_ema = ema_values(&prices, slow);
    let pairs: Vec<(f64, f64)> = fast_ema
        .iter()
        .zip(slow_ema.iter())
        .filter_map(|(f, s)| Some(((*f)?, (*s)?)))
        .collect();

    if pairs.len() < 2 {
        out.set_item("signal", "NEUTRAL")?;
        out.set_item("ema_fast", py.None())?;
        out.set_item("ema_slow", py.None())?;
        out.set_item("cross", false)?;
        return Ok(out.into());
    }

    let (cur_f, cur_s) = pairs[pairs.len() - 1];
    let (prev_f, prev_s) = pairs[pairs.len() - 2];
    let signal = if cur_f > cur_s { "BULL" } else { "BEAR" };
    let cross = (prev_f <= prev_s && cur_f > cur_s) || (prev_f >= prev_s && cur_f < cur_s);

    out.set_item("signal", signal)?;
    out.set_item("ema_fast", cur_f)?;
    out.set_item("ema_slow", cur_s)?;
    out.set_item("cross", cross)?;
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (prices, fast = 12, slow = 26, signal = 9))]
fn calculate_macd(
    py: Python<'_>,
    prices: &Bound<'_, PyAny>,
    fast: usize,
    slow: usize,
    signal: usize,
) -> PyResult<Py<PyAny>> {
    let prices = floats(prices)?;
    let out = PyDict::new(py);

    if fast == 12 && slow == 26 && signal == 9 {
        let raw = macd_raw(&prices);
        out.set_item("macd_line", raw.macd_line)?;
        out.set_item("signal_line", raw.signal_line)?;
        out.set_item("histogram", raw.histogram)?;
        out.set_item("direction", raw.direction)?;
        return Ok(out.into());
    }

    if prices.len() < slow + signal || fast == 0 || slow == 0 || signal == 0 {
        out.set_item("macd_line", 0.0)?;
        out.set_item("signal_line", 0.0)?;
        out.set_item("histogram", 0.0)?;
        out.set_item("direction", "─")?;
        return Ok(out.into());
    }

    let fast_ema = ema_values(&prices, fast);
    let slow_ema = ema_values(&prices, slow);
    let macd_line: Vec<f64> = fast_ema
        .iter()
        .zip(slow_ema.iter())
        .filter_map(|(f, s)| Some((*f)? - (*s)?))
        .collect();

    if macd_line.len() < signal {
        out.set_item("macd_line", 0.0)?;
        out.set_item("signal_line", 0.0)?;
        out.set_item("histogram", 0.0)?;
        out.set_item("direction", "─")?;
        return Ok(out.into());
    }

    let sig_line = ema_values(&macd_line, signal);
    let sig_vals: Vec<f64> = sig_line.into_iter().flatten().collect();
    if sig_vals.is_empty() {
        out.set_item("macd_line", 0.0)?;
        out.set_item("signal_line", 0.0)?;
        out.set_item("histogram", 0.0)?;
        out.set_item("direction", "─")?;
        return Ok(out.into());
    }

    let ml = *macd_line.last().unwrap();
    let sl = *sig_vals.last().unwrap();
    let hist = ml - sl;
    let hist_prev = if macd_line.len() >= 2 && sig_vals.len() >= 2 {
        macd_line[macd_line.len() - 2] - sig_vals[sig_vals.len() - 2]
    } else {
        hist
    };
    let direction = if hist > hist_prev { "UP" } else { "DOWN" };

    out.set_item("macd_line", round_to(ml, 6))?;
    out.set_item("signal_line", round_to(sl, 6))?;
    out.set_item("histogram", round_to(hist, 6))?;
    out.set_item("direction", direction)?;
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (prices, period = 20, std_mult = 2.0))]
fn calculate_bollinger(
    py: Python<'_>,
    prices: &Bound<'_, PyAny>,
    period: usize,
    std_mult: f64,
) -> PyResult<Py<PyAny>> {
    let prices = floats(prices)?;
    let out = PyDict::new(py);

    if period == 20 && std_mult == 2.0 {
        let raw = bollinger_raw(&prices);
        out.set_item("upper", raw.upper)?;
        out.set_item("middle", raw.middle)?;
        out.set_item("lower", raw.lower)?;
        out.set_item("pct_b", raw.pct_b)?;
        out.set_item("zone", raw.zone)?;
        out.set_item("bandwidth", raw.bandwidth)?;
        return Ok(out.into());
    }

    if prices.len() < period || period == 0 {
        out.set_item("upper", 0.0)?;
        out.set_item("middle", 0.0)?;
        out.set_item("lower", 0.0)?;
        out.set_item("pct_b", 0.5)?;
        out.set_item("zone", "MID")?;
        out.set_item("bandwidth", 0.0)?;
        return Ok(out.into());
    }

    let sample = &prices[prices.len() - period..];
    let mid = sum_f64(sample) / period as f64;
    let variance = sum_sq_diff_f64(sample, mid) / period as f64;
    let std = variance.sqrt();
    let upper = mid + std_mult * std;
    let lower = mid - std_mult * std;
    let price = *prices.last().unwrap();
    let band_range = if upper - lower != 0.0 {
        upper - lower
    } else {
        0.0001
    };
    let pct_b = (price - lower) / band_range;
    let bandwidth = if mid != 0.0 {
        (upper - lower) / mid * 100.0
    } else {
        0.0
    };
    let zone = if price > upper {
        "ABOVE"
    } else if pct_b >= 0.8 {
        "HIGH"
    } else if pct_b <= 0.2 {
        "LOW"
    } else if price < lower {
        "BELOW"
    } else {
        "MID"
    };

    out.set_item("upper", round_to(upper, 6))?;
    out.set_item("middle", round_to(mid, 6))?;
    out.set_item("lower", round_to(lower, 6))?;
    out.set_item("pct_b", round_to(pct_b, 3))?;
    out.set_item("zone", zone)?;
    out.set_item("bandwidth", round_to(bandwidth, 2))?;
    Ok(out.into())
}

#[pyfunction]
#[pyo3(signature = (highs, lows, closes, period = 14))]
fn calculate_atr(
    highs: &Bound<'_, PyAny>,
    lows: &Bound<'_, PyAny>,
    closes: &Bound<'_, PyAny>,
    period: usize,
) -> PyResult<f64> {
    let highs = floats(highs)?;
    let lows = floats(lows)?;
    let closes = floats(closes)?;
    if period == 14 {
        return Ok(atr_raw(&highs, &lows, &closes));
    }
    let n = highs.len().min(lows.len()).min(closes.len());

    if n < period + 1 || period == 0 {
        return Ok(0.0);
    }

    let mut trs = Vec::with_capacity(n - 1);
    for i in 1..n {
        let hl = highs[i] - lows[i];
        let hcp = (highs[i] - closes[i - 1]).abs();
        let lcp = (lows[i] - closes[i - 1]).abs();
        trs.push(hl.max(hcp).max(lcp));
    }

    if trs.len() < period {
        return Ok(0.0);
    }

    let mut atr = sum_f64(&trs[..period]) / period as f64;
    for tr in &trs[period..] {
        atr = (atr * (period as f64 - 1.0) + tr) / period as f64;
    }

    let price = closes[closes.len() - 1];
    Ok(if price != 0.0 {
        round_to(atr / price * 100.0, 3)
    } else {
        0.0
    })
}

#[pyfunction]
fn calculate_signal(
    py: Python<'_>,
    rsi: f64,
    ema_cross: &Bound<'_, PyDict>,
    macd: &Bound<'_, PyDict>,
    bb: &Bound<'_, PyDict>,
) -> PyResult<Py<PyAny>> {
    let mut score = 0;

    if rsi < 30.0 {
        score += 1;
    } else if rsi > 70.0 {
        score -= 1;
    }

    let ema_signal = ema_cross
        .get_item("signal")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_else(|| "NEUTRAL".to_string());
    if ema_signal == "BULL" {
        score += 1;
    } else if ema_signal == "BEAR" {
        score -= 1;
    }

    let cross = ema_cross
        .get_item("cross")?
        .and_then(|v| v.extract::<bool>().ok())
        .unwrap_or(false);
    if cross {
        score += if ema_signal == "BULL" { 1 } else { -1 };
    }

    let hist = macd
        .get_item("histogram")?
        .and_then(|v| v.extract::<f64>().ok())
        .unwrap_or(0.0);
    let direction = macd
        .get_item("direction")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_else(|| "─".to_string());
    if hist > 0.0 && direction == "UP" {
        score += 1;
    } else if hist < 0.0 && direction == "DOWN" {
        score -= 1;
    }

    let zone = bb
        .get_item("zone")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_else(|| "MID".to_string());
    if zone == "LOW" || zone == "BELOW" {
        score += 1;
    } else if zone == "HIGH" || zone == "ABOVE" {
        score -= 1;
    }

    let (sig, col, icon) = if score >= 3 {
        ("STR LONG", "bold bright_green", "●●")
    } else if score >= 1 {
        ("LONG", "green", "●○")
    } else if score <= -3 {
        ("STR SHORT", "bold bright_red", "●●")
    } else if score <= -1 {
        ("SHORT", "red", "●○")
    } else {
        ("NEUTRAL", "yellow", "○○")
    };

    let out = PyDict::new(py);
    out.set_item("score", score)?;
    out.set_item("signal", sig)?;
    out.set_item("color", col)?;
    out.set_item("icon", icon)?;
    Ok(out.into())
}

#[pyfunction]
fn relative_volume(vol_history: &Bound<'_, PyAny>, current_vol: f64) -> PyResult<f64> {
    let vol_history = floats(vol_history)?;
    Ok(relative_volume_raw(&vol_history, current_vol))
}

#[pyfunction]
fn calculate_indicator_bundle(
    py: Python<'_>,
    prices: &Bound<'_, PyAny>,
    highs: &Bound<'_, PyAny>,
    lows: &Bound<'_, PyAny>,
    vol_history: &Bound<'_, PyAny>,
    current_vol: f64,
) -> PyResult<Py<PyAny>> {
    let prices = floats(prices)?;
    let highs = floats(highs)?;
    let lows = floats(lows)?;
    let vol_history = floats(vol_history)?;

    let rsi = rsi_value(&prices, 14);
    let ((ema_raw, macd_raw), (bb_raw, ((atr, rvol), momentum_raw))) = join(
        || join(|| ema_cross_raw(&prices), || macd_raw(&prices)),
        || {
            join(
                || bollinger_raw(&prices),
                || {
                    join(
                        || {
                            join(
                                || atr_raw(&highs, &lows, &prices),
                                || relative_volume_raw(&vol_history, current_vol),
                            )
                        },
                        || momentum_raw(&prices),
                    )
                },
            )
        },
    );

    let ema = PyDict::new(py);
    ema.set_item("signal", ema_raw.signal)?;
    match ema_raw.ema_fast {
        Some(v) => ema.set_item("ema_fast", v)?,
        None => ema.set_item("ema_fast", py.None())?,
    }
    match ema_raw.ema_slow {
        Some(v) => ema.set_item("ema_slow", v)?,
        None => ema.set_item("ema_slow", py.None())?,
    }
    ema.set_item("cross", ema_raw.cross)?;

    let macd = PyDict::new(py);
    macd.set_item("macd_line", macd_raw.macd_line)?;
    macd.set_item("signal_line", macd_raw.signal_line)?;
    macd.set_item("histogram", macd_raw.histogram)?;
    macd.set_item("direction", macd_raw.direction)?;

    let bb = PyDict::new(py);
    bb.set_item("upper", bb_raw.upper)?;
    bb.set_item("middle", bb_raw.middle)?;
    bb.set_item("lower", bb_raw.lower)?;
    bb.set_item("pct_b", bb_raw.pct_b)?;
    bb.set_item("zone", bb_raw.zone)?;
    bb.set_item("bandwidth", bb_raw.bandwidth)?;

    let averages = PyDict::new(py);
    let sma = PyDict::new(py);
    let ema_avg = PyDict::new(py);
    match latest_sma_value(&prices, 20) {
        Some(v) => sma.set_item(20, v)?,
        None => sma.set_item(20, py.None())?,
    }
    match latest_sma_value(&prices, 50) {
        Some(v) => sma.set_item(50, v)?,
        None => sma.set_item(50, py.None())?,
    }
    for period in [9_usize, 21, 50] {
        match latest_ema_value(&prices, period) {
            Some(v) => ema_avg.set_item(period, v)?,
            None => ema_avg.set_item(period, py.None())?,
        }
    }
    averages.set_item("sma", sma)?;
    averages.set_item("ema", ema_avg)?;

    let momentum = PyDict::new(py);
    momentum.set_item("roc", momentum_raw.roc)?;
    momentum.set_item("state", momentum_raw.state)?;
    momentum.set_item("divergence", momentum_raw.divergence)?;
    momentum.set_item("squeeze", momentum_raw.squeeze)?;

    let mut score = 0;
    if rsi < 30.0 {
        score += 1;
    } else if rsi > 70.0 {
        score -= 1;
    }
    if ema_raw.signal == "BULL" {
        score += 1;
    } else if ema_raw.signal == "BEAR" {
        score -= 1;
    }
    if ema_raw.cross {
        score += if ema_raw.signal == "BULL" { 1 } else { -1 };
    }
    if macd_raw.histogram > 0.0 && macd_raw.direction == "UP" {
        score += 1;
    } else if macd_raw.histogram < 0.0 && macd_raw.direction == "DOWN" {
        score -= 1;
    }
    if bb_raw.zone == "LOW" || bb_raw.zone == "BELOW" {
        score += 1;
    } else if bb_raw.zone == "HIGH" || bb_raw.zone == "ABOVE" {
        score -= 1;
    }
    if momentum_raw.state == "BULL" {
        score += 1;
    } else if momentum_raw.state == "BEAR" {
        score -= 1;
    }
    if momentum_raw.divergence == "BULL" {
        score += 1;
    } else if momentum_raw.divergence == "BEAR" {
        score -= 1;
    }
    if momentum_raw.squeeze == "FIRED" {
        score += if macd_raw.histogram >= 0.0 { 1 } else { -1 };
    }
    let (sig, col, icon) = if score >= 3 {
        ("STR LONG", "bold bright_green", "OO")
    } else if score >= 1 {
        ("LONG", "green", "Oo")
    } else if score <= -3 {
        ("STR SHORT", "bold bright_red", "OO")
    } else if score <= -1 {
        ("SHORT", "red", "Oo")
    } else {
        ("NEUTRAL", "yellow", "oo")
    };
    let signal = PyDict::new(py);
    signal.set_item("score", score)?;
    signal.set_item("signal", sig)?;
    signal.set_item("color", col)?;
    signal.set_item("icon", icon)?;

    let out = PyDict::new(py);
    out.set_item("rsi", rsi)?;
    out.set_item("ema", ema)?;
    out.set_item("macd", macd)?;
    out.set_item("bb", bb)?;
    out.set_item("atr", atr)?;
    out.set_item("rvol", rvol)?;
    out.set_item("averages", averages)?;
    out.set_item("momentum", momentum)?;
    out.set_item("signal", signal)?;
    Ok(out.into())
}

#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_rsi, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_ema, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_ema_cross, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_macd, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_bollinger, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_atr, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_signal, m)?)?;
    m.add_function(wrap_pyfunction!(relative_volume, m)?)?;
    m.add_function(wrap_pyfunction!(calculate_indicator_bundle, m)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_approx(actual: f64, expected: f64, tolerance: f64) {
        assert!(
            (actual - expected).abs() <= tolerance,
            "expected {actual} to be within {tolerance} of {expected}"
        );
    }

    fn sequence(len: usize) -> Vec<f64> {
        (1..=len).map(|value| value as f64).collect()
    }

    #[test]
    fn rsi_returns_neutral_for_short_series() {
        assert_eq!(rsi_value(&[100.0, 101.0, 102.0], 14), 50.0);
    }

    #[test]
    fn rsi_detects_strong_uptrend() {
        let prices = sequence(30);

        assert_eq!(rsi_value(&prices, 14), 100.0);
    }

    #[test]
    fn ema_values_seed_with_sma_and_keep_input_length() {
        let values = ema_values(&sequence(10), 3);

        assert_eq!(values.len(), 10);
        assert_eq!(values[0], None);
        assert_eq!(values[1], None);
        assert_approx(values[2].unwrap(), 2.0, 1e-12);
        assert_approx(values[9].unwrap(), 9.0, 1e-12);
    }

    #[test]
    fn ema_cross_marks_clear_uptrend_as_bullish() {
        let prices = sequence(60);
        let cross = ema_cross_raw(&prices);

        assert_eq!(cross.signal, "BULL");
        assert!(!cross.cross);
        assert!(cross.ema_fast.unwrap() > cross.ema_slow.unwrap());
    }

    #[test]
    fn macd_marks_clear_uptrend_as_positive_momentum() {
        let prices = sequence(80);
        let macd = macd_raw(&prices);

        assert!(macd.macd_line > 0.0);
        assert!(macd.signal_line > 0.0);
        assert_approx(macd.histogram, 0.0, 1e-6);
        assert_eq!(macd.direction, "DOWN");
    }

    #[test]
    fn bollinger_matches_known_twenty_point_window() {
        let bands = bollinger_raw(&sequence(20));

        assert_approx(bands.middle, 10.5, 1e-6);
        assert_approx(bands.upper, 22.032563, 1e-6);
        assert_approx(bands.lower, -1.032563, 1e-6);
        assert_eq!(bands.pct_b, 0.912);
        assert_eq!(bands.zone, "HIGH");
        assert_eq!(bands.bandwidth, 219.67);
    }

    #[test]
    fn atr_returns_percent_of_latest_close() {
        let closes = sequence(20);
        let highs: Vec<f64> = closes.iter().map(|price| price + 1.0).collect();
        let lows: Vec<f64> = closes.iter().map(|price| price - 1.0).collect();

        assert_eq!(atr_raw(&highs, &lows, &closes), 10.0);
    }

    #[test]
    fn relative_volume_uses_recent_average() {
        let history = sequence(20);

        assert_eq!(relative_volume_raw(&history, 21.0), 2.0);
    }

    #[test]
    fn momentum_classifies_ten_period_rate_of_change() {
        let bullish = momentum_raw(&sequence(30));
        let bearish_prices: Vec<f64> = (1..=30).rev().map(|value| value as f64).collect();
        let bearish = momentum_raw(&bearish_prices);

        assert_eq!(bullish.state, "BULL");
        assert!(bullish.roc > 0.0);
        assert_eq!(bearish.state, "BEAR");
        assert!(bearish.roc < 0.0);
    }
}

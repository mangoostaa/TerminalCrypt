use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

#[cfg(target_arch = "x86")]
use std::arch::x86::{
    __m256d, _mm256_add_pd, _mm256_loadu_pd, _mm256_set1_pd, _mm256_setzero_pd,
    _mm256_storeu_pd, _mm256_sub_pd, _mm256_mul_pd,
};
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::{
    __m256d, _mm256_add_pd, _mm256_loadu_pd, _mm256_set1_pd, _mm256_setzero_pd,
    _mm256_storeu_pd, _mm256_sub_pd, _mm256_mul_pd,
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
    ema_values(prices, period)
        .into_iter()
        .flatten()
        .last()
        .map(|v| round_to(v, 6))
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

fn momentum_value(prices: &[f64], period: usize) -> (f64, &'static str, &'static str, &'static str) {
    if prices.len() <= period {
        return (0.0, "NEUTRAL", "-", "-");
    }

    let prev = prices[prices.len() - period - 1];
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

        let rsi_series = rsi_series_values(prices, 14);
        let left_rsi = rsi_series[prices.len() - 30..prices.len() - 15]
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max);
        let right_rsi = rsi_series[prices.len() - 15..]
            .iter()
            .copied()
            .fold(f64::NEG_INFINITY, f64::max);
        let left_rsi_low = rsi_series[prices.len() - 30..prices.len() - 15]
            .iter()
            .copied()
            .fold(f64::INFINITY, f64::min);
        let right_rsi_low = rsi_series[prices.len() - 15..]
            .iter()
            .copied()
            .fold(f64::INFINITY, f64::min);

        if right_high > left_high && right_rsi < left_rsi {
            divergence = "BEAR";
        } else if right_low < left_low && right_rsi_low > left_rsi_low {
            divergence = "BULL";
        }
    }

    let widths = bollinger_bandwidth_values(prices, 20, 2.0);
    let mut squeeze = "-";
    if widths.len() >= 20 {
        let recent = *widths.last().unwrap();
        let mut baseline = widths[widths.len() - 20..].to_vec();
        baseline.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let idx = ((baseline.len() as f64 * 0.2) as usize).saturating_sub(1);
        let threshold = baseline[idx];
        if recent <= threshold {
            squeeze = "ON";
        } else if widths.len() >= 2 && widths[widths.len() - 2] <= threshold && threshold < recent {
            squeeze = "FIRED";
        }
    }

    (round_to(roc, 2), state, divergence, squeeze)
}

fn rsi_series_values(prices: &[f64], period: usize) -> Vec<f64> {
    let mut out = Vec::with_capacity(prices.len());
    for end in 1..=prices.len() {
        out.push(rsi_value(&prices[..end], period));
    }
    out
}

fn bollinger_bandwidth_values(prices: &[f64], period: usize, std_mult: f64) -> Vec<f64> {
    let mut values = Vec::new();
    if period == 0 || prices.len() < period {
        return values;
    }
    for i in period..=prices.len() {
        let sample = &prices[i - period..i];
        let mid = sum_f64(sample) / period as f64;
        let variance = sum_sq_diff_f64(sample, mid) / period as f64;
        let std = variance.sqrt();
        values.push(if mid != 0.0 {
            (std_mult * 2.0 * std) / mid * 100.0
        } else {
            0.0
        });
    }
    values
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
    let band_range = if upper - lower != 0.0 { upper - lower } else { 0.0001 };
    let pct_b = (price - lower) / band_range;
    let bandwidth = if mid != 0.0 { (upper - lower) / mid * 100.0 } else { 0.0 };
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
    if vol_history.len() < 10 || current_vol <= 0.0 {
        return Ok(1.0);
    }

    let start = vol_history.len().saturating_sub(20);
    let sample = &vol_history[start..];
    let avg_vol = sum_f64(sample) / sample.len() as f64;
    Ok(if avg_vol > 0.0 {
        round_to(current_vol / avg_vol, 2)
    } else {
        1.0
    })
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

    let ema = PyDict::new(py);
    if prices.len() < 22 {
        ema.set_item("signal", "NEUTRAL")?;
        ema.set_item("ema_fast", py.None())?;
        ema.set_item("ema_slow", py.None())?;
        ema.set_item("cross", false)?;
    } else {
        let fast_ema = ema_values(&prices, 9);
        let slow_ema = ema_values(&prices, 21);
        let pairs: Vec<(f64, f64)> = fast_ema
            .iter()
            .zip(slow_ema.iter())
            .filter_map(|(f, s)| Some(((*f)?, (*s)?)))
            .collect();
        if pairs.len() < 2 {
            ema.set_item("signal", "NEUTRAL")?;
            ema.set_item("ema_fast", py.None())?;
            ema.set_item("ema_slow", py.None())?;
            ema.set_item("cross", false)?;
        } else {
            let (cur_f, cur_s) = pairs[pairs.len() - 1];
            let (prev_f, prev_s) = pairs[pairs.len() - 2];
            let signal = if cur_f > cur_s { "BULL" } else { "BEAR" };
            let cross = (prev_f <= prev_s && cur_f > cur_s) || (prev_f >= prev_s && cur_f < cur_s);
            ema.set_item("signal", signal)?;
            ema.set_item("ema_fast", cur_f)?;
            ema.set_item("ema_slow", cur_s)?;
            ema.set_item("cross", cross)?;
        }
    }

    let macd = PyDict::new(py);
    if prices.len() < 35 {
        macd.set_item("macd_line", 0.0)?;
        macd.set_item("signal_line", 0.0)?;
        macd.set_item("histogram", 0.0)?;
        macd.set_item("direction", "-")?;
    } else {
        let fast_ema = ema_values(&prices, 12);
        let slow_ema = ema_values(&prices, 26);
        let macd_line: Vec<f64> = fast_ema
            .iter()
            .zip(slow_ema.iter())
            .filter_map(|(f, s)| Some((*f)? - (*s)?))
            .collect();
        let sig_line = ema_values(&macd_line, 9);
        let sig_vals: Vec<f64> = sig_line.into_iter().flatten().collect();
        if macd_line.is_empty() || sig_vals.is_empty() {
            macd.set_item("macd_line", 0.0)?;
            macd.set_item("signal_line", 0.0)?;
            macd.set_item("histogram", 0.0)?;
            macd.set_item("direction", "-")?;
        } else {
            let ml = *macd_line.last().unwrap();
            let sl = *sig_vals.last().unwrap();
            let hist = ml - sl;
            let hist_prev = if macd_line.len() >= 2 && sig_vals.len() >= 2 {
                macd_line[macd_line.len() - 2] - sig_vals[sig_vals.len() - 2]
            } else {
                hist
            };
            macd.set_item("macd_line", round_to(ml, 6))?;
            macd.set_item("signal_line", round_to(sl, 6))?;
            macd.set_item("histogram", round_to(hist, 6))?;
            macd.set_item("direction", if hist > hist_prev { "UP" } else { "DOWN" })?;
        }
    }

    let bb = PyDict::new(py);
    if prices.len() < 20 {
        bb.set_item("upper", 0.0)?;
        bb.set_item("middle", 0.0)?;
        bb.set_item("lower", 0.0)?;
        bb.set_item("pct_b", 0.5)?;
        bb.set_item("zone", "MID")?;
        bb.set_item("bandwidth", 0.0)?;
    } else {
        let sample = &prices[prices.len() - 20..];
        let mid = sum_f64(sample) / 20.0;
        let variance = sum_sq_diff_f64(sample, mid) / 20.0;
        let std = variance.sqrt();
        let upper = mid + 2.0 * std;
        let lower = mid - 2.0 * std;
        let price = *prices.last().unwrap();
        let band_range = if upper - lower != 0.0 { upper - lower } else { 0.0001 };
        let pct_b = (price - lower) / band_range;
        let bandwidth = if mid != 0.0 { (upper - lower) / mid * 100.0 } else { 0.0 };
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
        bb.set_item("upper", round_to(upper, 6))?;
        bb.set_item("middle", round_to(mid, 6))?;
        bb.set_item("lower", round_to(lower, 6))?;
        bb.set_item("pct_b", round_to(pct_b, 3))?;
        bb.set_item("zone", zone)?;
        bb.set_item("bandwidth", round_to(bandwidth, 2))?;
    }

    let n = highs.len().min(lows.len()).min(prices.len());
    let atr = if n < 15 {
        0.0
    } else {
        let mut trs = Vec::with_capacity(n - 1);
        for i in 1..n {
            let hl = highs[i] - lows[i];
            let hcp = (highs[i] - prices[i - 1]).abs();
            let lcp = (lows[i] - prices[i - 1]).abs();
            trs.push(hl.max(hcp).max(lcp));
        }
        let mut atr = sum_f64(&trs[..14]) / 14.0;
        for tr in &trs[14..] {
            atr = (atr * 13.0 + tr) / 14.0;
        }
        let price = *prices.last().unwrap_or(&0.0);
        if price != 0.0 { round_to(atr / price * 100.0, 3) } else { 0.0 }
    };

    let rvol = if vol_history.len() < 10 || current_vol <= 0.0 {
        1.0
    } else {
        let start = vol_history.len().saturating_sub(20);
        let sample = &vol_history[start..];
        let avg_vol = sum_f64(sample) / sample.len() as f64;
        if avg_vol > 0.0 { round_to(current_vol / avg_vol, 2) } else { 1.0 }
    };

    let (roc, momentum_state, divergence, squeeze) = momentum_value(&prices, 10);

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
    momentum.set_item("roc", roc)?;
    momentum.set_item("state", momentum_state)?;
    momentum.set_item("divergence", divergence)?;
    momentum.set_item("squeeze", squeeze)?;

    let mut score = 0;
    if rsi < 30.0 {
        score += 1;
    } else if rsi > 70.0 {
        score -= 1;
    }
    let ema_signal = ema
        .get_item("signal")?
        .and_then(|v| v.extract::<String>().ok())
        .unwrap_or_else(|| "NEUTRAL".to_string());
    if ema_signal == "BULL" {
        score += 1;
    } else if ema_signal == "BEAR" {
        score -= 1;
    }
    let cross = ema
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
        .unwrap_or_else(|| "-".to_string());
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
    if momentum_state == "BULL" {
        score += 1;
    } else if momentum_state == "BEAR" {
        score -= 1;
    }
    if divergence == "BULL" {
        score += 1;
    } else if divergence == "BEAR" {
        score -= 1;
    }
    if squeeze == "FIRED" {
        score += if hist >= 0.0 { 1 } else { -1 };
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

use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};

fn floats(values: &Bound<'_, PyAny>) -> PyResult<Vec<f64>> {
    values.extract::<Vec<f64>>()
}

fn round_to(value: f64, decimals: i32) -> f64 {
    let scale = 10_f64.powi(decimals);
    (value * scale).round() / scale
}

fn ema_values(prices: &[f64], period: usize) -> Vec<Option<f64>> {
    if period == 0 || prices.len() < period {
        return vec![None; prices.len()];
    }

    let k = 2.0 / (period as f64 + 1.0);
    let mut result = vec![None; period - 1];
    let mut prev = prices[..period].iter().sum::<f64>() / period as f64;
    result.push(Some(prev));

    for price in &prices[period..] {
        prev = price * k + prev * (1.0 - k);
        result.push(Some(prev));
    }

    result
}

#[pyfunction]
#[pyo3(signature = (prices, period = 14))]
fn calculate_rsi(prices: &Bound<'_, PyAny>, period: usize) -> PyResult<f64> {
    let prices = floats(prices)?;
    if prices.len() < period + 1 || period == 0 {
        return Ok(50.0);
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
    Ok(round_to(100.0 - (100.0 / (1.0 + rs)), 1))
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
    let mid = sample.iter().sum::<f64>() / period as f64;
    let variance = sample.iter().map(|p| (p - mid).powi(2)).sum::<f64>() / period as f64;
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

    let mut atr = trs[..period].iter().sum::<f64>() / period as f64;
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
    let avg_vol = sample.iter().sum::<f64>() / sample.len() as f64;
    Ok(if avg_vol > 0.0 {
        round_to(current_vol / avg_vol, 2)
    } else {
        1.0
    })
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
    Ok(())
}

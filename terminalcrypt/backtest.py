"""Walk-forward backtesting for the built-in signal engine.

The backtester replays historical candles one bar at a time, recomputing the
same indicator bundle the live dashboard uses, and simulates entering/exiting
positions from the combined signal score. It never looks ahead: the position
decided on bar ``i`` (using data up to and including its close) only earns the
return of bar ``i+1``.

Results are plain dicts so they are trivial to test and to render.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

from .indicators import calculate_indicator_bundle

log = logging.getLogger(__name__)

# Bars of history required before the engine is allowed to open a position.
DEFAULT_WARMUP = 50


@dataclass(frozen=True)
class BacktestConfig:
    entry_threshold: int = 3   # |score| at/above which we open a position
    exit_threshold: int = 1    # |score| below which we flatten an open position
    allow_short: bool = True   # trade both directions or long-only
    fee_pct: float = 0.05      # taker fee per side, percent of notional
    warmup: int = DEFAULT_WARMUP


def _target_position(score: int, current: int, cfg: BacktestConfig) -> int:
    """Map a signal score + current position to a desired position.

    Uses hysteresis: a position is only closed once the score falls back inside
    the ``exit_threshold`` band, which avoids churning on small oscillations.
    """
    if score >= cfg.entry_threshold:
        return 1
    if score <= -cfg.entry_threshold and cfg.allow_short:
        return -1
    if abs(score) < cfg.exit_threshold:
        return 0
    return current


def _sharpe(returns: list[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    std = math.sqrt(var)
    if std == 0:
        return 0.0
    # Annualized against 1-minute bars (525,600 minutes per year) as a rough,
    # comparable figure; scale is exchange/timeframe agnostic for ranking.
    return round(mean / std * math.sqrt(525_600), 2)


def _max_drawdown(equity: list[float]) -> float:
    peak = equity[0] if equity else 1.0
    max_dd = 0.0
    for value in equity:
        peak = max(peak, value)
        if peak > 0:
            max_dd = min(max_dd, (value - peak) / peak)
    return round(max_dd * 100, 2)


def run_backtest(candles: list[dict], cfg: BacktestConfig | None = None) -> dict:
    """Replay ``candles`` and return performance metrics.

    ``candles`` is a list of dicts with ``open/high/low/close/volume`` keys, as
    produced by :mod:`terminalcrypt.history`.
    """
    cfg = cfg or BacktestConfig()
    closes = [float(c["close"]) for c in candles]
    highs = [float(c.get("high", c["close"])) for c in candles]
    lows = [float(c.get("low", c["close"])) for c in candles]
    vols = [float(c.get("volume", 0) or 0) for c in candles]
    n = len(closes)

    result = {
        "bars": n,
        "trades": 0,
        "wins": 0,
        "losses": 0,
        "win_rate": 0.0,
        "return_pct": 0.0,
        "buy_hold_pct": 0.0,
        "max_drawdown_pct": 0.0,
        "sharpe": 0.0,
        "exposure_pct": 0.0,
        "avg_win_pct": 0.0,
        "avg_loss_pct": 0.0,
        "trade_log": [],
    }
    if n <= cfg.warmup + 2:
        return result

    fee = cfg.fee_pct / 100.0
    equity = 1.0
    equity_curve = [1.0]
    strat_returns: list[float] = []
    position = 0
    entry_price = 0.0
    entry_idx = 0
    bars_in_market = 0
    trade_returns: list[float] = []
    trade_log: list[dict] = []

    for i in range(cfg.warmup, n - 1):
        window = slice(0, i + 1)
        bundle = calculate_indicator_bundle(
            closes[window], highs[window], lows[window], vols[window],
            candles[window], vols[i],
        )
        score = int(bundle["signal"]["score"])
        target = _target_position(score, position, cfg)

        # Realize a closed/flipped trade on the decision bar's close.
        if target != position and position != 0:
            exit_price = closes[i]
            gross = (exit_price - entry_price) / entry_price * position
            net = gross - 2 * fee  # entry + exit fees
            trade_returns.append(net * 100)
            trade_log.append({
                "side": "LONG" if position > 0 else "SHORT",
                "entry": round(entry_price, 6),
                "exit": round(exit_price, 6),
                "bars": i - entry_idx,
                "pnl_pct": round(net * 100, 3),
            })
        if target != position and target != 0:
            entry_price = closes[i]
            entry_idx = i

        position = target

        # Apply the *next* bar's return to the position we now hold.
        nxt = (closes[i + 1] - closes[i]) / closes[i] if closes[i] else 0.0
        bar_ret = position * nxt
        equity *= 1 + bar_ret
        equity_curve.append(equity)
        strat_returns.append(bar_ret)
        if position != 0:
            bars_in_market += 1

    # Close any open position at the final close.
    if position != 0:
        exit_price = closes[-1]
        gross = (exit_price - entry_price) / entry_price * position
        net = gross - 2 * fee
        trade_returns.append(net * 100)
        trade_log.append({
            "side": "LONG" if position > 0 else "SHORT",
            "entry": round(entry_price, 6),
            "exit": round(exit_price, 6),
            "bars": (n - 1) - entry_idx,
            "pnl_pct": round(net * 100, 3),
        })

    wins = [r for r in trade_returns if r > 0]
    losses = [r for r in trade_returns if r <= 0]
    traded_bars = max(n - 1 - cfg.warmup, 1)
    buy_hold = (closes[-1] - closes[cfg.warmup]) / closes[cfg.warmup] * 100 if closes[cfg.warmup] else 0.0

    result.update({
        "trades": len(trade_returns),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(trade_returns) * 100, 1) if trade_returns else 0.0,
        "return_pct": round((equity - 1) * 100, 2),
        "buy_hold_pct": round(buy_hold, 2),
        "max_drawdown_pct": _max_drawdown(equity_curve),
        "sharpe": _sharpe(strat_returns),
        "exposure_pct": round(bars_in_market / traded_bars * 100, 1),
        "avg_win_pct": round(sum(wins) / len(wins), 3) if wins else 0.0,
        "avg_loss_pct": round(sum(losses) / len(losses), 3) if losses else 0.0,
        "trade_log": trade_log[-20:],
    })
    return result

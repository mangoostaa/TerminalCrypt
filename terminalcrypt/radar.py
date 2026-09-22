"""Opportunity Radar: multi-factor real-time setup scanner.

Where the basic scanner (:mod:`terminalcrypt.scanner`) ranks by a single
dimension (movers, volume, signal), the radar fuses several confirming factors
into one directional *conviction* score, explains itself with human-readable
reasons, and attaches concrete, ATR-based trade levels (entry, stop, targets,
risk/reward).

Factors considered (long or short, whichever the signal favours):

* Volatility squeeze firing (Bollinger bandwidth expansion) — the trigger.
* Relative volume (RVOL) confirmation.
* Fresh EMA 9/21 cross and prevailing EMA trend.
* MACD histogram sign and direction.
* RSI / price divergence.
* Bollinger zone reclaim or breakout.
* VWAP reclaim / rejection.
* Rate-of-change magnitude.

The core :func:`build_opportunity` is pure — it takes the analytics dict the
dashboard already computes — so it is fully unit-testable without the network.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Tunables.
MIN_SCORE = 45.0        # below this, not worth surfacing
MAX_SPREAD_PCT = 0.6    # skip illiquid books
ATR_STOP_MULT = 1.5     # stop distance = mult * ATR
DEFAULT_ATR_PCT = 1.5   # fallback volatility when ATR is unavailable


@dataclass
class Opportunity:
    sym: str
    direction: str            # "LONG" or "SHORT"
    score: float              # 0..100 conviction
    price: float
    entry: float
    stop: float
    targets: list[float]
    risk_reward: float
    reasons: list[str] = field(default_factory=list)
    rsi: float = 50.0
    rvol: float = 1.0
    atr_pct: float = 0.0
    spread: float = 0.0
    chg24: float = 0.0

    def as_dict(self) -> dict:
        return {
            "sym": self.sym, "direction": self.direction, "score": round(self.score, 1),
            "price": self.price, "entry": self.entry, "stop": self.stop,
            "targets": self.targets, "risk_reward": self.risk_reward,
            "reasons": self.reasons, "rsi": self.rsi, "rvol": self.rvol,
            "atr_pct": self.atr_pct, "spread": self.spread, "chg24": self.chg24,
        }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def build_opportunity(sym: str, price: float, spread: float, analytics: dict,
                      chg24: float = 0.0) -> Opportunity | None:
    """Score one symbol into an :class:`Opportunity`, or ``None`` if flat.

    ``analytics`` is the dict returned by ``AnalyticsCache.indicators``.
    """
    if price <= 0:
        return None

    signal = analytics.get("signal", {})
    ema = analytics.get("ema", {})
    macd = analytics.get("macd", {})
    bb = analytics.get("bb", {})
    mom = analytics.get("momentum", {})
    rsi = float(analytics.get("rsi", 50.0))
    rvol = float(analytics.get("rvol", 1.0))
    atr_pct = float(analytics.get("atr", 0.0))
    vwap = analytics.get("vwap")

    sig_score = int(signal.get("score", 0))
    # Direction: signal score, falling back to EMA trend.
    if sig_score >= 1:
        direction = "LONG"
    elif sig_score <= -1:
        direction = "SHORT"
    elif ema.get("signal") == "BULL":
        direction = "LONG"
    elif ema.get("signal") == "BEAR":
        direction = "SHORT"
    else:
        return None
    dir_sign = 1 if direction == "LONG" else -1

    score = 30.0 + abs(sig_score) * 4.0
    reasons: list[str] = []

    squeeze = mom.get("squeeze", "-")
    if squeeze == "FIRED":
        score += 22
        reasons.append("squeeze disparado")
    elif squeeze == "ON":
        score += 6
        reasons.append("compresión (squeeze)")

    if rvol >= 2.5:
        score += 18
        reasons.append(f"volumen {rvol:.1f}x")
    elif rvol >= 1.5:
        score += 8
        reasons.append(f"volumen {rvol:.1f}x")

    ema_sig = ema.get("signal")
    if ema.get("cross") and ((ema_sig == "BULL") == (direction == "LONG")):
        score += 16
        reasons.append(f"cruce EMA {ema_sig}")
    elif (ema_sig == "BULL") == (direction == "LONG") and ema_sig in ("BULL", "BEAR"):
        score += 8
        reasons.append(f"tendencia EMA {ema_sig}")

    hist = macd.get("histogram", 0.0)
    mdir = macd.get("direction", "-")
    if (hist > 0) == (direction == "LONG") and mdir in ("UP", "DOWN") and (mdir == "UP") == (direction == "LONG"):
        score += 10
        reasons.append(f"MACD {'▲' if direction == 'LONG' else '▼'}")

    divergence = mom.get("divergence", "-")
    if divergence == ("BULL" if direction == "LONG" else "SHORT") or divergence == ("BULL" if direction == "LONG" else "BEAR"):
        score += 14
        reasons.append(f"divergencia {divergence}")

    zone = bb.get("zone", "MID")
    if direction == "LONG" and zone in ("LOW", "BELOW"):
        score += 10
        reasons.append("reclamo desde banda inferior")
    elif direction == "SHORT" and zone in ("HIGH", "ABOVE"):
        score += 10
        reasons.append("rechazo en banda superior")
    elif direction == "LONG" and zone == "ABOVE":
        score += 6
        reasons.append("ruptura sobre banda")

    if vwap:
        if direction == "LONG" and price > vwap:
            score += 6
            reasons.append("sobre VWAP")
        elif direction == "SHORT" and price < vwap:
            score += 6
            reasons.append("bajo VWAP")

    roc = float(mom.get("roc", 0.0))
    if (roc > 0) == (direction == "LONG") and abs(roc) >= 0.5:
        score += _clamp(abs(roc), 0, 5) * 1.4
        reasons.append(f"momentum {roc:+.1f}%")

    # Liquidity penalty.
    if spread:
        score -= _clamp(spread * 20, 0, 15)

    score = _clamp(score, 0, 100)

    # ATR-based trade levels.
    eff_atr = atr_pct if atr_pct > 0 else DEFAULT_ATR_PCT
    atr_abs = price * eff_atr / 100.0
    stop_dist = ATR_STOP_MULT * atr_abs
    if stop_dist <= 0:
        return None
    if direction == "LONG":
        stop = price - stop_dist
        targets = [round(price + i * stop_dist, 8) for i in (1, 2, 3)]
    else:
        stop = price + stop_dist
        targets = [round(price - i * stop_dist, 8) for i in (1, 2, 3)]
    risk_reward = 2.0  # targets are R multiples; T2 = 2R

    return Opportunity(
        sym=sym, direction=direction, score=score, price=price,
        entry=round(price, 8), stop=round(stop, 8), targets=targets,
        risk_reward=risk_reward, reasons=reasons or ["señal base"],
        rsi=rsi, rvol=rvol, atr_pct=atr_pct, spread=spread, chg24=chg24,
    )


def scan_opportunities(snapshot: dict, cache, min_score: float = MIN_SCORE,
                       max_spread: float = MAX_SPREAD_PCT, limit: int = 12,
                       direction: str | None = None) -> list[dict]:
    """Scan every active symbol and return ranked opportunities as dicts.

    ``cache`` is an :class:`~terminalcrypt.analytics.AnalyticsCache`. ``direction``
    optionally filters to only ``"LONG"`` or ``"SHORT"`` setups.
    """
    prices = snapshot.get("prices", {})
    spreads = snapshot.get("spread", {})
    chg = snapshot.get("chg24h", {})
    out: list[Opportunity] = []
    for sym, price in prices.items():
        if not price:
            continue
        spread = float(spreads.get(sym, 0) or 0)
        if spread and spread > max_spread:
            continue
        analytics = cache.indicators(sym, snapshot)
        if len(analytics.get("history", [])) < 25:
            continue  # not enough data for a confident read
        opp = build_opportunity(sym, price, spread, analytics, float(chg.get(sym, 0) or 0))
        if opp and opp.score >= min_score and (direction is None or opp.direction == direction):
            out.append(opp)
    out.sort(key=lambda o: o.score, reverse=True)
    return [o.as_dict() for o in out[:limit]]

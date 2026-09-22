"""Micro-benchmark for the indicator engine: pure Python vs the Rust backend.

The full indicator *bundle* (RSI, EMA cross, MACD, Bollinger, ATR, RVOL,
momentum/squeeze/divergence, signal) is what runs for every symbol on every
tick, so that is what we time. The Rust backend additionally uses AVX2 SIMD for
the sum / sum-of-squared-deviations kernels and rayon to compute the sub-
indicators in parallel.

Usage::

    python benchmarks/bench_indicators.py            # compare both backends
    python benchmarks/bench_indicators.py --single    # time the loaded backend only

``--compare`` (the default) re-runs this script in two subprocesses — one with
``TERMINALCRYPT_NO_NATIVE=1`` to force pure Python — so each measurement uses a
genuinely separate backend with no cross-contamination.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import subprocess
import sys
import time

# Allow running straight from a checkout without installing the package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

WINDOW = 120        # candles per symbol (matches HISTORY_MAX)
ITERATIONS = 20_000
SYMBOLS = 80        # for the "full market scan" projection


def _make_data(n: int = WINDOW):
    prices = [100 + 15 * math.sin(i / 9) + i * 0.05 for i in range(n)]
    highs = [p * 1.004 for p in prices]
    lows = [p * 0.996 for p in prices]
    vols = [1000 + 500 * math.sin(i / 5) for i in range(n)]
    return prices, highs, lows, vols


def _time_backend(iterations: int = ITERATIONS) -> dict:
    from terminalcrypt import indicators

    prices, highs, lows, vols = _make_data()
    candles = [
        {"open": p, "high": h, "low": l, "close": p, "volume": v}
        for p, h, l, v in zip(prices, highs, lows, vols)
    ]

    # Warm up (JIT-free, but primes caches / branch predictors).
    for _ in range(500):
        indicators.calculate_indicator_bundle(prices, highs, lows, vols, candles, vols[-1])

    best = math.inf
    for _ in range(5):  # take the best of a few runs to reduce noise
        t0 = time.perf_counter()
        for _ in range(iterations):
            indicators.calculate_indicator_bundle(prices, highs, lows, vols, candles, vols[-1])
        elapsed = time.perf_counter() - t0
        best = min(best, elapsed)

    per_call_us = best / iterations * 1e6
    return {
        "backend": indicators._BACKEND,
        "iterations": iterations,
        "per_call_us": round(per_call_us, 3),
        "calls_per_sec": round(iterations / best),
        "market_scan_ms": round(per_call_us * SYMBOLS / 1000, 3),
    }


def _run_single() -> None:
    print(json.dumps(_time_backend()))


def _run_compare() -> None:
    env_native = dict(os.environ)
    env_native.pop("TERMINALCRYPT_NO_NATIVE", None)
    env_python = dict(os.environ, TERMINALCRYPT_NO_NATIVE="1")

    def child(env) -> dict:
        out = subprocess.check_output([sys.executable, os.path.abspath(__file__), "--single"], env=env)
        return json.loads(out.decode().strip().splitlines()[-1])

    native = child(env_native)
    py = child(env_python)

    print(f"CPU:    {platform.processor() or platform.machine()}")
    print(f"Python: {platform.python_version()} ({platform.system()})")
    print(f"Window: {WINDOW} candles · {ITERATIONS:,} iterations · best of 5\n")

    header = f"{'backend':<10} {'per call':>12} {'calls/sec':>14} {'80-sym scan':>14} {'speedup':>9}"
    print(header)
    print("-" * len(header))
    base = py["per_call_us"]
    for row in (py, native):
        speedup = base / row["per_call_us"] if row["per_call_us"] else 1.0
        print(f"{row['backend']:<10} {row['per_call_us']:>10.2f}µs "
              f"{row['calls_per_sec']:>14,} {row['market_scan_ms']:>12.2f}ms {speedup:>8.1f}x")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", action="store_true", help="time only the currently-loaded backend (JSON)")
    args = ap.parse_args()
    if args.single:
        _run_single()
    else:
        _run_compare()

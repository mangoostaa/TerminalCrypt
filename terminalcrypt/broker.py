"""Paper-trading broker with simulated execution.

A self-contained, dependency-free simulated exchange account: cash balance,
signed positions (long and short), market and resting limit orders, fees and
slippage, realized/unrealized P&L, an equity curve, and JSON persistence.

Execution model
---------------
* Market orders fill immediately against the last price with symmetric
  ``slippage_pct`` (buys pay up, sells receive less).
* Limit orders rest until :meth:`on_prices` sees the market cross the limit,
  then fill at the limit price.
* No leverage on the long side: a buy is rejected if cash cannot cover it.
  Shorts are allowed (proceeds are credited; the negative position is a
  liability marked to market).

All monetary values are in the quote currency (USD). Nothing here touches the
network — it is driven entirely by prices handed in by the caller.
"""

from __future__ import annotations

import json
import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

EQUITY_CURVE_MAX = 240


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class OrderError(Exception):
    """Raised when an order cannot be accepted (bad input or insufficient cash)."""


class PaperBroker:
    def __init__(self, cash: float = 10_000.0, fee_pct: float = 0.05, slippage_pct: float = 0.02):
        self.starting_cash = float(cash)
        self.cash = float(cash)
        self.fee_pct = float(fee_pct) / 100.0
        self.slippage_pct = float(slippage_pct) / 100.0
        # symbol -> {"qty": signed float, "avg": float, "realized": float}
        self.positions: dict[str, dict] = {}
        self.open_orders: list[dict] = []
        self.fills: list[dict] = []
        self._seq = 0
        self.equity_curve: deque = deque(maxlen=EQUITY_CURVE_MAX)

    # ------------------------------------------------------------------ helpers
    def _pos(self, sym: str) -> dict:
        return self.positions.setdefault(sym, {"qty": 0.0, "avg": 0.0, "realized": 0.0})

    def position_qty(self, sym: str) -> float:
        return self.positions.get(sym, {}).get("qty", 0.0)

    def _record_fill(self, order: dict, price: float) -> None:
        self.fills.append({
            "id": order["id"],
            "ts": _now(),
            "symbol": order["symbol"],
            "side": order["side"],
            "type": order["type"],
            "qty": order["qty"],
            "price": round(price, 8),
            "notional": round(price * order["qty"], 2),
        })

    def _apply_fill(self, sym: str, side: str, qty: float, price: float) -> None:
        """Update cash and the position for a fill. Realizes P&L on reductions."""
        signed = qty if side == "buy" else -qty
        notional = price * qty
        fee = notional * self.fee_pct
        self.cash += (-notional - fee) if side == "buy" else (notional - fee)

        pos = self._pos(sym)
        old_qty, old_avg = pos["qty"], pos["avg"]
        new_qty = old_qty + signed

        if old_qty == 0 or (old_qty > 0) == (signed > 0):
            # Opening or increasing in the same direction: weighted-average entry.
            total = abs(old_qty) + qty
            pos["avg"] = (old_avg * abs(old_qty) + price * qty) / total if total else price
        else:
            # Reducing, closing, or flipping the position.
            closing = min(qty, abs(old_qty))
            direction = 1 if old_qty > 0 else -1
            pos["realized"] += (price - old_avg) * closing * direction
            if abs(signed) > abs(old_qty):      # flipped through zero
                pos["avg"] = price
            elif new_qty == 0:
                pos["avg"] = 0.0
            # else: partial reduction keeps the original average entry
        pos["qty"] = new_qty

    # ------------------------------------------------------------------- orders
    def market_order(self, sym: str, side: str, qty: float, price: float) -> dict:
        sym = sym.upper()
        side = side.lower()
        if side not in ("buy", "sell"):
            raise OrderError(f"lado inválido: {side}")
        if qty <= 0 or price <= 0:
            raise OrderError("cantidad y precio deben ser positivos")

        fill_price = price * (1 + self.slippage_pct) if side == "buy" else price * (1 - self.slippage_pct)
        # No leverage: a buy that opens/increases a long must be covered by cash.
        if side == "buy" and self.position_qty(sym) >= 0:
            cost = fill_price * qty * (1 + self.fee_pct)
            if cost > self.cash + 1e-9:
                raise OrderError(f"efectivo insuficiente: cuesta ${cost:,.2f}, disponible ${self.cash:,.2f}")

        self._seq += 1
        order = {
            "id": self._seq, "ts": _now(), "symbol": sym, "side": side,
            "type": "market", "qty": float(qty), "limit_price": None,
            "status": "filled", "fill_price": round(fill_price, 8),
        }
        self._apply_fill(sym, side, qty, fill_price)
        self._record_fill(order, fill_price)
        log.info("paper %s %s %g @ %.6f", side, sym, qty, fill_price)
        return order

    def market_notional(self, sym: str, side: str, notional: float, price: float) -> dict:
        if price <= 0:
            raise OrderError("precio inválido")
        if notional <= 0:
            raise OrderError("notional debe ser positivo")
        return self.market_order(sym, side, notional / price, price)

    def limit_order(self, sym: str, side: str, qty: float, limit_price: float) -> dict:
        sym = sym.upper()
        side = side.lower()
        if side not in ("buy", "sell"):
            raise OrderError(f"lado inválido: {side}")
        if qty <= 0 or limit_price <= 0:
            raise OrderError("cantidad y precio límite deben ser positivos")
        self._seq += 1
        order = {
            "id": self._seq, "ts": _now(), "symbol": sym, "side": side,
            "type": "limit", "qty": float(qty), "limit_price": float(limit_price),
            "status": "open", "fill_price": None,
        }
        self.open_orders.append(order)
        return order

    def cancel(self, order_id: int) -> bool:
        for o in self.open_orders:
            if o["id"] == order_id:
                self.open_orders.remove(o)
                return True
        return False

    def close(self, sym: str, price: float) -> dict | None:
        qty = self.position_qty(sym.upper())
        if qty == 0:
            return None
        side = "sell" if qty > 0 else "buy"
        return self.market_order(sym, side, abs(qty), price)

    def on_prices(self, prices: dict[str, float]) -> list[dict]:
        """Fill any resting limit orders the market has crossed. Returns fills."""
        filled = []
        for o in list(self.open_orders):
            price = float(prices.get(o["symbol"], 0) or 0)
            if price <= 0:
                continue
            crossed = (o["side"] == "buy" and price <= o["limit_price"]) or \
                      (o["side"] == "sell" and price >= o["limit_price"])
            if not crossed:
                continue
            try:
                self._apply_fill(o["symbol"], o["side"], o["qty"], o["limit_price"])
            except OrderError as e:
                log.warning("limit fill rejected %s: %s", o["id"], e)
                continue
            o["status"] = "filled"
            o["fill_price"] = o["limit_price"]
            self._record_fill(o, o["limit_price"])
            self.open_orders.remove(o)
            filled.append(o)
        return filled

    # --------------------------------------------------------------- valuation
    def evaluate(self, prices: dict[str, float]) -> dict:
        positions = []
        pos_value = 0.0
        unrealized_total = 0.0
        realized_total = 0.0
        for sym, pos in self.positions.items():
            qty = pos["qty"]
            realized_total += pos["realized"]
            if qty == 0:
                continue
            mark = float(prices.get(sym, 0) or 0)
            market_value = mark * qty
            unrealized = (mark - pos["avg"]) * qty if mark else 0.0
            pos_value += market_value
            unrealized_total += unrealized
            positions.append({
                "symbol": sym,
                "side": "LONG" if qty > 0 else "SHORT",
                "qty": qty,
                "avg": pos["avg"],
                "mark": mark,
                "market_value": market_value,
                "unrealized": unrealized,
                "unrealized_pct": ((mark - pos["avg"]) / pos["avg"] * 100 * (1 if qty > 0 else -1)) if pos["avg"] else 0.0,
                "realized": pos["realized"],
                "priced": mark > 0,
            })
        positions.sort(key=lambda p: abs(p["market_value"]), reverse=True)
        equity = self.cash + pos_value
        return {
            "cash": self.cash,
            "starting_cash": self.starting_cash,
            "positions": positions,
            "position_value": pos_value,
            "equity": equity,
            "unrealized": unrealized_total,
            "realized": realized_total,
            "total_pnl": equity - self.starting_cash,
            "total_pnl_pct": (equity - self.starting_cash) / self.starting_cash * 100 if self.starting_cash else 0.0,
            "open_orders": list(self.open_orders),
            "fills": self.fills[-15:],
            "equity_curve": list(self.equity_curve),
            "fill_count": len(self.fills),
        }

    def mark(self, prices: dict[str, float]) -> float:
        """Append current equity to the curve and return it."""
        equity = self.cash + sum(
            (float(prices.get(s, 0) or 0)) * p["qty"] for s, p in self.positions.items() if p["qty"]
        )
        self.equity_curve.append(round(equity, 2))
        return equity

    # ------------------------------------------------------------- persistence
    def to_dict(self) -> dict:
        return {
            "starting_cash": self.starting_cash,
            "cash": self.cash,
            "fee_pct": self.fee_pct * 100,
            "slippage_pct": self.slippage_pct * 100,
            "positions": self.positions,
            "open_orders": self.open_orders,
            "fills": self.fills,
            "seq": self._seq,
            "equity_curve": list(self.equity_curve),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PaperBroker":
        b = cls(
            cash=float(data.get("starting_cash", data.get("cash", 10_000.0))),
            fee_pct=float(data.get("fee_pct", 0.05)),
            slippage_pct=float(data.get("slippage_pct", 0.02)),
        )
        b.cash = float(data.get("cash", b.cash))
        b.positions = {k: {"qty": float(v.get("qty", 0)), "avg": float(v.get("avg", 0)), "realized": float(v.get("realized", 0))}
                       for k, v in data.get("positions", {}).items()}
        b.open_orders = list(data.get("open_orders", []))
        b.fills = list(data.get("fills", []))
        b._seq = int(data.get("seq", 0))
        b.equity_curve = deque(data.get("equity_curve", []), maxlen=EQUITY_CURVE_MAX)
        return b

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path, default_cash: float = 10_000.0,
             fee_pct: float = 0.05, slippage_pct: float = 0.02) -> "PaperBroker":
        path = Path(path)
        if not path.exists():
            return cls(default_cash, fee_pct, slippage_pct)
        try:
            with path.open("r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
            log.warning("could not load paper account %s: %s", path, e)
            return cls(default_cash, fee_pct, slippage_pct)

    def export_fills_csv(self, path: str | Path) -> int:
        """Write the fill history to a CSV. Returns the number of rows written."""
        import csv
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fields = ["id", "ts", "symbol", "side", "type", "qty", "price", "notional"]
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for fill in self.fills:
                writer.writerow({k: fill.get(k, "") for k in fields})
        return len(self.fills)

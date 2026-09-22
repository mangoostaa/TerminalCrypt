"""Portfolio tracking: holdings, cost basis, and live P&L.

Holdings are loaded from a small JSON or TOML file. Each holding names an asset
symbol (matching the dashboard symbols such as ``BTC``), a quantity, and an
average ``cost_basis`` per unit. Given a live price map the portfolio computes
market value, unrealized profit/loss, and allocation for each position plus the
book as a whole.

Example ``portfolio.json``::

    {
      "holdings": [
        {"symbol": "BTC", "quantity": 0.5, "cost_basis": 42000},
        {"symbol": "ETH", "quantity": 4,   "cost_basis": 3000}
      ]
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    tomllib = None

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Holding:
    symbol: str
    quantity: float
    cost_basis: float  # average cost per unit


class Portfolio:
    def __init__(self, holdings: list[Holding] | None = None):
        self.holdings: list[Holding] = holdings or []

    @classmethod
    def from_dict(cls, data: dict) -> "Portfolio":
        holdings = []
        for raw in data.get("holdings", []):
            try:
                sym = str(raw["symbol"]).upper()
                qty = float(raw["quantity"])
                cost = float(raw.get("cost_basis", raw.get("cost", 0)) or 0)
            except (KeyError, TypeError, ValueError) as e:
                log.warning("skipping malformed holding %r: %s", raw, e)
                continue
            if qty != 0:
                holdings.append(Holding(sym, qty, cost))
        return cls(holdings)

    @classmethod
    def load(cls, path: str | Path) -> "Portfolio":
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"portfolio file not found: {path}")
        if path.suffix.lower() == ".toml":
            if tomllib is None:
                raise RuntimeError("TOML portfolios require Python 3.11+ (tomllib)")
            with path.open("rb") as f:
                data = tomllib.load(f)
            data = data.get("portfolio", data)
        else:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        return cls.from_dict(data)

    def evaluate(self, prices: dict[str, float]) -> dict:
        """Return per-position and aggregate valuation against ``prices``."""
        positions = []
        total_value = 0.0
        total_cost = 0.0
        for h in self.holdings:
            price = float(prices.get(h.symbol, 0) or 0)
            value = price * h.quantity
            cost = h.cost_basis * h.quantity
            pnl = value - cost
            pnl_pct = (pnl / cost * 100) if cost else 0.0
            total_value += value
            total_cost += cost
            positions.append({
                "symbol": h.symbol,
                "quantity": h.quantity,
                "cost_basis": h.cost_basis,
                "price": price,
                "value": value,
                "cost": cost,
                "pnl": pnl,
                "pnl_pct": round(pnl_pct, 2),
                "priced": price > 0,
            })

        for pos in positions:
            pos["allocation_pct"] = round(pos["value"] / total_value * 100, 2) if total_value else 0.0

        positions.sort(key=lambda p: p["value"], reverse=True)
        total_pnl = total_value - total_cost
        return {
            "positions": positions,
            "total_value": total_value,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "total_pnl_pct": round(total_pnl / total_cost * 100, 2) if total_cost else 0.0,
            "count": len(positions),
        }

    @property
    def symbols(self) -> list[str]:
        return [h.symbol for h in self.holdings]

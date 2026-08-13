from __future__ import annotations

import math
import statistics
from datetime import datetime
from typing import Any

PERPETUAL_CONTRACT_TYPES = {"PERPETUAL", "PERPETUAL_DELIVERING"}
DELIVERY_CONTRACT_TYPES = {
    "CURRENT_MONTH",
    "NEXT_MONTH",
    "CURRENT_QUARTER",
    "NEXT_QUARTER",
}
SUPPORTED_CONTRACT_TYPES = PERPETUAL_CONTRACT_TYPES | DELIVERY_CONTRACT_TYPES


def periods_per_year(interval: str) -> float:
    """Return observation periods per 365-day crypto trading year."""
    if not interval:
        raise ValueError("Kline interval is required for annualization")
    unit = interval[-1]
    try:
        count = int(interval[:-1])
    except ValueError as exc:
        raise ValueError(f"Invalid kline interval: {interval}") from exc
    if count <= 0:
        raise ValueError(f"Invalid kline interval: {interval}")
    if unit == "s":
        return 365 * 24 * 60 * 60 / count
    if unit == "m":
        return 365 * 24 * 60 / count
    if unit == "h":
        return 365 * 24 / count
    if unit == "d":
        return 365 / count
    if unit == "w":
        return 365 / (7 * count)
    if unit == "M":
        return 12 / count
    raise ValueError(f"Unsupported kline interval: {interval}")


def _positive_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be numeric") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def _utc_datetime(value: Any, name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} is required")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed


def basis_percent(spot_price: float, futures_price: float) -> float:
    return (futures_price / spot_price - 1.0) * 100.0


def annualized_delivery_basis_percent(
    spot_price: float,
    futures_price: float,
    days_to_maturity: float,
) -> float:
    if days_to_maturity <= 0:
        raise ValueError("Cannot annualize observations at or after contract delivery")
    return basis_percent(spot_price, futures_price) * 365.0 / days_to_maturity


def annualized_funding_simple_percent(rate: float, interval_hours: float) -> float:
    if not math.isfinite(rate):
        raise ValueError("funding_rate must be finite")
    if not math.isfinite(interval_hours) or interval_hours <= 0:
        raise ValueError("funding_interval_hours must be finite and positive")
    return rate * (365.0 * 24.0 / interval_hours) * 100.0


def annualized_spot_volatility(spot_prices: list[float], interval: str) -> float:
    if len(spot_prices) < 3:
        raise ValueError("spot_prices requires at least three observations")
    prices = [_positive_number(value, "spot price") for value in spot_prices]
    returns = [prices[index] / prices[index - 1] - 1.0 for index in range(1, len(prices))]
    return statistics.stdev(returns) * math.sqrt(periods_per_year(interval))


def calculate_scenario(snapshot: dict[str, Any], overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Calculate contract-aware metrics from a committed snapshot plus explicit scenario overrides.

    This function performs no network or filesystem I/O and is the canonical calculation
    entry point shared by CPython tests and the Pyodide Web Worker.
    """
    if snapshot.get("schema_version") != "option.browser-scenario.v1":
        raise ValueError("unsupported browser scenario snapshot schema")
    market = snapshot.get("market")
    contract = snapshot.get("contract")
    if not isinstance(market, dict) or not isinstance(contract, dict):
        raise ValueError("snapshot market and contract objects are required")
    overrides = overrides or {}
    allowed = {
        "contract_type",
        "delivery_time",
        "interval",
        "futures_price",
        "funding_rate",
        "funding_interval_hours",
    }
    unknown = set(overrides) - allowed
    if unknown:
        raise ValueError(f"unsupported scenario override(s): {', '.join(sorted(unknown))}")

    spot_prices = market.get("spot_prices")
    if not isinstance(spot_prices, list) or not spot_prices:
        raise ValueError("snapshot spot_prices are required")
    spot_price = _positive_number(spot_prices[-1], "spot_price")
    futures_price = _positive_number(
        overrides.get("futures_price", market.get("futures_price")),
        "futures_price",
    )
    interval = str(overrides.get("interval", snapshot.get("interval") or ""))
    observation = _utc_datetime(snapshot.get("observation_time"), "observation_time")
    contract_type = str(overrides.get("contract_type", contract.get("contract_type") or "")).upper()
    if contract_type not in SUPPORTED_CONTRACT_TYPES:
        raise ValueError(f"Unsupported or missing futures contract type: {contract_type!r}")

    premium = basis_percent(spot_price, futures_price)
    result: dict[str, Any] = {
        "schema_version": "option.browser-scenario-result.v1",
        "symbol": contract.get("symbol"),
        "contract_type": contract_type,
        "observation_time": snapshot["observation_time"],
        "interval": interval,
        "spot_price": spot_price,
        "futures_price": futures_price,
        "basis": futures_price - spot_price,
        "basis_percent": premium,
        "perpetual_premium_pct": None,
        "days_to_maturity": None,
        "annualized_basis": None,
        "annualization_method": None,
        "funding_interval_hours": None,
        "funding_annualized_simple_pct": None,
        "spot_volatility": annualized_spot_volatility(spot_prices, interval),
        "provenance": snapshot.get("provenance"),
    }

    if contract_type in PERPETUAL_CONTRACT_TYPES:
        result["perpetual_premium_pct"] = premium
        result["annualization_method"] = "not_applicable_perpetual"
    else:
        delivery_value = overrides.get("delivery_time", contract.get("delivery_time"))
        delivery = _utc_datetime(delivery_value, "delivery_time")
        days_to_maturity = (delivery - observation).total_seconds() / 86_400.0
        result["days_to_maturity"] = days_to_maturity
        result["annualized_basis"] = annualized_delivery_basis_percent(
            spot_price,
            futures_price,
            days_to_maturity,
        )
        result["annualization_method"] = "simple_actual_dte_365"

    funding_rate = overrides.get("funding_rate", market.get("funding_rate"))
    funding_interval = overrides.get(
        "funding_interval_hours",
        market.get("funding_interval_hours"),
    )
    if funding_rate is not None or funding_interval is not None:
        if funding_rate is None or funding_interval is None:
            raise ValueError("funding_rate and funding_interval_hours must be supplied together")
        funding_rate_number = float(funding_rate)
        funding_interval_number = float(funding_interval)
        result["funding_interval_hours"] = funding_interval_number
        result["funding_annualized_simple_pct"] = annualized_funding_simple_percent(
            funding_rate_number,
            funding_interval_number,
        )

    volatility = result["spot_volatility"]
    result["vol_adjusted_basis"] = premium / volatility if volatility else None
    return result

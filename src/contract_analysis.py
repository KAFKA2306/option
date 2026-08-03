from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from advanced_analysis import BitcoinBasisAnalyzer

PERPETUAL_CONTRACT_TYPES = {"PERPETUAL", "PERPETUAL_DELIVERING"}
DELIVERY_CONTRACT_TYPES = {
    "CURRENT_MONTH",
    "NEXT_MONTH",
    "CURRENT_QUARTER",
    "NEXT_QUARTER",
}


@dataclass(frozen=True)
class ContractMetadata:
    symbol: str
    contract_type: str
    status: str | None
    delivery_datetime: pd.Timestamp | None
    onboard_datetime: pd.Timestamp | None
    underlying_type: str | None

    @property
    def is_perpetual(self) -> bool:
        return self.contract_type in PERPETUAL_CONTRACT_TYPES

    @property
    def is_delivery(self) -> bool:
        return self.contract_type in DELIVERY_CONTRACT_TYPES


def _timestamp_from_milliseconds(value: Any) -> pd.Timestamp | None:
    if value in {None, "", 0, "0"}:
        return None
    try:
        return pd.to_datetime(int(value), unit="ms", utc=True)
    except (TypeError, ValueError, OverflowError):
        return None


def contract_metadata_from_frame(frame: pd.DataFrame) -> ContractMetadata:
    raw = frame.attrs.get("contract_metadata", {})
    if not isinstance(raw, dict):
        raw = {}

    def first(column: str) -> Any:
        if column not in frame or frame[column].dropna().empty:
            return None
        return frame[column].dropna().iloc[0]

    symbol = str(raw.get("symbol") or first("contract_symbol") or "").upper()
    contract_type = str(
        raw.get("contractType")
        or raw.get("contract_type")
        or first("contract_type")
        or ""
    ).upper()
    if not symbol:
        raise ValueError("Futures contract symbol metadata is required")
    if contract_type not in PERPETUAL_CONTRACT_TYPES | DELIVERY_CONTRACT_TYPES:
        raise ValueError(f"Unsupported or missing futures contract type: {contract_type!r}")

    delivery_value = raw.get("deliveryDate") or raw.get("delivery_datetime") or first(
        "delivery_datetime"
    )
    onboard_value = raw.get("onboardDate") or raw.get("onboard_datetime") or first(
        "onboard_datetime"
    )
    delivery = (
        pd.Timestamp(delivery_value)
        if isinstance(delivery_value, (pd.Timestamp, str)) and delivery_value
        else _timestamp_from_milliseconds(delivery_value)
    )
    onboard = (
        pd.Timestamp(onboard_value)
        if isinstance(onboard_value, (pd.Timestamp, str)) and onboard_value
        else _timestamp_from_milliseconds(onboard_value)
    )
    if delivery is not None and delivery.tzinfo is None:
        delivery = delivery.tz_localize("UTC")
    if onboard is not None and onboard.tzinfo is None:
        onboard = onboard.tz_localize("UTC")

    return ContractMetadata(
        symbol=symbol,
        contract_type=contract_type,
        status=(str(raw.get("status") or first("contract_status")) or None),
        delivery_datetime=delivery,
        onboard_datetime=onboard,
        underlying_type=(
            str(raw.get("underlyingType") or first("underlying_type")) or None
        ),
    )


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


def observation_times_utc(index: pd.Index) -> pd.DatetimeIndex:
    values = pd.DatetimeIndex(pd.to_datetime(index))
    if values.tz is None:
        return values.tz_localize("UTC")
    return values.tz_convert("UTC")


class ContractAwareBitcoinBasisAnalyzer(BitcoinBasisAnalyzer):
    """Basis analyzer that separates perpetual premium from delivery basis."""

    def __init__(
        self,
        spot_df: pd.DataFrame,
        futures_df: pd.DataFrame,
        *,
        interval: str,
    ) -> None:
        self.interval = interval
        self.contract_metadata = contract_metadata_from_frame(futures_df)
        super().__init__(spot_df, futures_df)
        self._attach_contract_and_funding_evidence(futures_df)

    def _attach_contract_and_funding_evidence(self, futures_df: pd.DataFrame) -> None:
        metadata = self.contract_metadata
        self.basis_df["contract_symbol"] = metadata.symbol
        self.basis_df["contract_type"] = metadata.contract_type
        self.basis_df["contract_status"] = metadata.status
        self.basis_df["delivery_datetime"] = metadata.delivery_datetime
        self.basis_df["annualization_day_count"] = 365.0

        for column in ("funding_rate", "funding_time", "funding_mark_price"):
            if column in futures_df:
                self.basis_df[column] = futures_df.loc[self.basis_df.index, column]

        if "funding_rate" in self.basis_df:
            self.basis_df["funding_rate"] = pd.to_numeric(
                self.basis_df["funding_rate"], errors="coerce"
            )
            funding_times = pd.to_datetime(
                self.basis_df.get("funding_time"),
                errors="coerce",
                utc=True,
            ).dropna()
            unique_times = pd.DatetimeIndex(funding_times.unique()).sort_values()
            if len(unique_times) >= 2:
                intervals = pd.Series(unique_times).diff().dropna().dt.total_seconds() / 3600
                funding_interval_hours = float(intervals.median())
            else:
                funding_interval_hours = math.nan
            self.basis_df["funding_interval_hours"] = funding_interval_hours
            if funding_interval_hours > 0:
                payments_per_year = 365 * 24 / funding_interval_hours
                self.basis_df["funding_annualized_simple_pct"] = (
                    self.basis_df["funding_rate"] * payments_per_year * 100
                )
            else:
                self.basis_df["funding_annualized_simple_pct"] = np.nan

    def calculate_annualized_basis(self) -> pd.Series:
        metadata = self.contract_metadata
        raw_premium = self.basis_df["futures_price"] / self.basis_df["spot_price"] - 1

        if metadata.is_perpetual:
            self.basis_df["perpetual_premium_pct"] = raw_premium * 100
            self.basis_df["days_to_maturity"] = np.nan
            self.basis_df["annualized_basis"] = np.nan
            self.basis_df["annualization_method"] = "not_applicable_perpetual"
            return self.basis_df["annualized_basis"]

        if not metadata.is_delivery or metadata.delivery_datetime is None:
            raise ValueError(
                "Delivery contracts require a supported contract type and delivery datetime"
            )

        observations = observation_times_utc(self.basis_df.index)
        days_to_maturity = (
            metadata.delivery_datetime - observations
        ).total_seconds() / 86_400
        if np.any(days_to_maturity <= 0):
            raise ValueError("Cannot annualize observations at or after contract delivery")

        self.basis_df["perpetual_premium_pct"] = np.nan
        self.basis_df["days_to_maturity"] = days_to_maturity
        self.basis_df["annualized_basis"] = raw_premium * (365 / days_to_maturity) * 100
        self.basis_df["annualization_method"] = "simple_actual_dte_365"
        return self.basis_df["annualized_basis"]

    def calculate_volatility_adjusted_basis(self, vol_window: int = 30) -> pd.Series:
        spot_returns = self.basis_df["spot_price"].pct_change()
        annualization_factor = periods_per_year(self.interval)
        self.basis_df["volatility_periods_per_year"] = annualization_factor
        self.basis_df["spot_volatility"] = (
            spot_returns.rolling(window=vol_window).std()
            * np.sqrt(annualization_factor)
        )
        self.basis_df["vol_adjusted_basis"] = (
            self.basis_df["basis_percent"] / self.basis_df["spot_volatility"]
        )
        return self.basis_df["vol_adjusted_basis"]

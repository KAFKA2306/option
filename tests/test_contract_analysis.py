from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contract_analysis import (  # noqa: E402
    ContractAwareBitcoinBasisAnalyzer,
    periods_per_year,
)


class ContractAwareBasisTests(unittest.TestCase):
    def frames(
        self,
        *,
        index: pd.DatetimeIndex,
        contract_type: str,
        delivery: pd.Timestamp | None = None,
        funding: bool = False,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        spot = pd.DataFrame({"close": np.full(len(index), 100.0)}, index=index)
        futures = pd.DataFrame({"close": np.full(len(index), 101.0)}, index=index)
        metadata = {
            "symbol": "BTCUSDT",
            "contractType": contract_type,
            "status": "TRADING",
            "onboardDate": int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000),
            "deliveryDate": (
                int(delivery.timestamp() * 1000)
                if delivery is not None
                else int(pd.Timestamp("2100-01-01", tz="UTC").timestamp() * 1000)
            ),
            "underlyingType": "COIN",
        }
        futures.attrs["contract_metadata"] = metadata
        if funding:
            futures["funding_rate"] = [0.0001, 0.0002, 0.0001]
            futures["funding_time"] = pd.to_datetime(
                [
                    "2026-08-01T00:00:00Z",
                    "2026-08-01T08:00:00Z",
                    "2026-08-01T16:00:00Z",
                ]
            )
        return spot, futures

    def test_perpetual_contract_has_premium_but_no_annualized_basis(self) -> None:
        index = pd.date_range("2026-08-01", periods=2, freq="h")
        spot, futures = self.frames(index=index, contract_type="PERPETUAL")
        analyzer = ContractAwareBitcoinBasisAnalyzer(
            spot,
            futures,
            interval="1h",
        )

        annualized = analyzer.calculate_annualized_basis()

        self.assertTrue(annualized.isna().all())
        self.assertTrue(analyzer.basis_df["days_to_maturity"].isna().all())
        self.assertTrue(
            np.allclose(analyzer.basis_df["perpetual_premium_pct"], 1.0)
        )
        self.assertEqual(
            analyzer.basis_df["annualization_method"].iloc[0],
            "not_applicable_perpetual",
        )

    def test_delivery_contract_uses_actual_days_to_maturity(self) -> None:
        observation = pd.Timestamp("2026-08-01T00:00:00Z")
        expected = {
            5: 73.0,
            30: 365 / 30,
            90: 365 / 90,
        }
        for days, expected_percent in expected.items():
            with self.subTest(days=days):
                index = pd.DatetimeIndex([observation.tz_localize(None)])
                spot, futures = self.frames(
                    index=index,
                    contract_type="CURRENT_QUARTER",
                    delivery=observation + pd.Timedelta(days=days),
                )
                analyzer = ContractAwareBitcoinBasisAnalyzer(
                    spot,
                    futures,
                    interval="1d",
                )
                result = analyzer.calculate_annualized_basis()
                self.assertAlmostEqual(
                    analyzer.basis_df["days_to_maturity"].iloc[0],
                    days,
                )
                self.assertAlmostEqual(result.iloc[0], expected_percent, places=9)
                self.assertEqual(
                    analyzer.basis_df["annualization_method"].iloc[0],
                    "simple_actual_dte_365",
                )

    def test_observation_at_or_after_delivery_is_rejected(self) -> None:
        observation = pd.Timestamp("2026-08-01T00:00:00Z")
        index = pd.DatetimeIndex([observation.tz_localize(None)])
        spot, futures = self.frames(
            index=index,
            contract_type="CURRENT_QUARTER",
            delivery=observation,
        )
        analyzer = ContractAwareBitcoinBasisAnalyzer(
            spot,
            futures,
            interval="1d",
        )
        with self.assertRaisesRegex(ValueError, "at or after contract delivery"):
            analyzer.calculate_annualized_basis()

    def test_funding_interval_is_inferred_without_assuming_30_day_maturity(self) -> None:
        index = pd.date_range("2026-08-01", periods=3, freq="8h")
        spot, futures = self.frames(
            index=index,
            contract_type="PERPETUAL",
            funding=True,
        )
        analyzer = ContractAwareBitcoinBasisAnalyzer(
            spot,
            futures,
            interval="8h",
        )
        self.assertEqual(analyzer.basis_df["funding_interval_hours"].iloc[0], 8.0)
        expected = 0.0001 * (365 * 24 / 8) * 100
        self.assertAlmostEqual(
            analyzer.basis_df["funding_annualized_simple_pct"].iloc[0],
            expected,
        )

    def test_interval_specific_periods_per_year(self) -> None:
        self.assertEqual(periods_per_year("1m"), 365 * 24 * 60)
        self.assertEqual(periods_per_year("1h"), 365 * 24)
        self.assertEqual(periods_per_year("1d"), 365)
        self.assertAlmostEqual(periods_per_year("1w"), 365 / 7)
        self.assertEqual(periods_per_year("1M"), 12)
        self.assertNotEqual(periods_per_year("1h"), 252)

    def test_unknown_contract_type_fails_closed(self) -> None:
        index = pd.date_range("2026-08-01", periods=1, freq="h")
        spot, futures = self.frames(index=index, contract_type="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "Unsupported or missing"):
            ContractAwareBitcoinBasisAnalyzer(spot, futures, interval="1h")


if __name__ == "__main__":
    unittest.main()

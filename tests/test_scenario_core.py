from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from contract_analysis import ContractAwareBitcoinBasisAnalyzer  # noqa: E402
from scenario_core import calculate_scenario  # noqa: E402


class BrowserScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshot = json.loads((ROOT / "scenario" / "snapshot.json").read_text(encoding="utf-8"))

    def test_perpetual_fixture_matches_existing_python_analyzer(self) -> None:
        index = pd.date_range("2026-08-01T00:00:00", periods=3, freq="8h")
        spot = pd.DataFrame({"close": [98.0, 99.0, 100.0]}, index=index)
        futures = pd.DataFrame({"close": [99.0, 100.0, 101.0]}, index=index)
        futures.attrs["contract_metadata"] = {
            "symbol": "BTCUSDT",
            "contractType": "PERPETUAL",
            "status": "TRADING",
            "deliveryDate": int(pd.Timestamp("2100-01-01", tz="UTC").timestamp() * 1000),
            "onboardDate": int(pd.Timestamp("2024-01-01", tz="UTC").timestamp() * 1000),
            "underlyingType": "COIN",
        }
        futures["funding_rate"] = [0.0001, 0.0002, 0.0001]
        futures["funding_time"] = pd.to_datetime([
            "2026-08-01T00:00:00Z",
            "2026-08-01T08:00:00Z",
            "2026-08-01T16:00:00Z",
        ])
        analyzer = ContractAwareBitcoinBasisAnalyzer(spot, futures, interval="8h")
        analyzer.calculate_annualized_basis()
        analyzer.calculate_volatility_adjusted_basis(vol_window=2)
        expected = analyzer.basis_df.iloc[-1]

        result = calculate_scenario(self.snapshot)

        self.assertAlmostEqual(result["basis_percent"], float(expected["basis_percent"]), places=12)
        self.assertAlmostEqual(result["perpetual_premium_pct"], float(expected["perpetual_premium_pct"]), places=12)
        self.assertIsNone(result["days_to_maturity"])
        self.assertIsNone(result["annualized_basis"])
        self.assertEqual(result["annualization_method"], "not_applicable_perpetual")
        self.assertAlmostEqual(result["funding_interval_hours"], float(expected["funding_interval_hours"]), places=12)
        self.assertAlmostEqual(result["funding_annualized_simple_pct"], float(expected["funding_annualized_simple_pct"]), places=12)
        self.assertAlmostEqual(result["spot_volatility"], float(expected["spot_volatility"]), places=12)
        self.assertAlmostEqual(result["vol_adjusted_basis"], float(expected["vol_adjusted_basis"]), places=12)

    def test_delivery_scenario_uses_actual_dte(self) -> None:
        result = calculate_scenario(self.snapshot, {
            "contract_type": "CURRENT_QUARTER",
            "delivery_time": "2026-08-31T16:00:00+00:00",
        })
        self.assertAlmostEqual(result["days_to_maturity"], 30.0)
        self.assertAlmostEqual(result["annualized_basis"], 365.0 / 30.0, places=12)
        self.assertIsNone(result["perpetual_premium_pct"])
        self.assertEqual(result["annualization_method"], "simple_actual_dte_365")

    def test_delivery_at_observation_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "at or after contract delivery"):
            calculate_scenario(self.snapshot, {
                "contract_type": "CURRENT_QUARTER",
                "delivery_time": self.snapshot["observation_time"],
            })

    def test_unknown_contract_type_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported or missing"):
            calculate_scenario(self.snapshot, {"contract_type": "UNKNOWN"})

    def test_browser_boundary_has_no_market_client_or_financial_formula(self) -> None:
        app = (ROOT / "scenario" / "app.js").read_text(encoding="utf-8")
        worker = (ROOT / "scenario" / "worker.mjs").read_text(encoding="utf-8")
        core = (ROOT / "src" / "scenario_core.py").read_text(encoding="utf-8")
        html = (ROOT / "scenario.html").read_text(encoding="utf-8")
        browser = (app + worker + html).lower()
        self.assertNotIn("binance.com", browser)
        self.assertNotIn("api.binance", browser)
        self.assertNotIn("365 /", app)
        self.assertNotIn("futures_price /", app)
        self.assertIn("calculate_scenario", worker)
        self.assertIn("scenario_core.py", worker)
        self.assertIn("v314.0.2", worker)
        self.assertIn("type: \"module\"", app)
        for dependency in ("pandas", "numpy", "matplotlib", "seaborn", "sklearn"):
            self.assertNotIn(f"import {dependency}", core)
        self.assertIn("scenario/app.js", html)


if __name__ == "__main__":
    unittest.main()

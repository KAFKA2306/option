import unittest

from src.carry_monitor import build_monitor, validate_watchlist


BASE_WATCHLIST = {
    "schema_version": "carry-watchlist.v1",
    "id": "btc-sample",
    "version": "1.0.0",
    "entries": [
        {
            "id": "btc-perp",
            "spot_symbol": "BTCUSDT",
            "futures_symbol": "BTCUSDT",
            "expected_contract_type": "PERPETUAL",
            "enabled": True,
            "thresholds": {"premium_pct": 1.0, "funding_rate": 0.001},
        }
    ],
}


class CarryMonitorTests(unittest.TestCase):
    def build(self, rows, previous=None, watchlist=None):
        return build_monitor(
            rows,
            watchlist or BASE_WATCHLIST,
            retrieved_at="2026-08-10T08:00:00Z",
            commit_sha="abc123",
            source_endpoint="binance-test-fixture",
            previous=previous,
        )

    def test_perpetual_never_emits_delivery_basis(self):
        result = self.build([{
            "contract_symbol": "BTCUSDT",
            "contract_type": "PERPETUAL",
            "contract_status": "TRADING",
            "spot_price": 100.0,
            "futures_price": 100.5,
            "perpetual_premium_pct": 0.5,
            "funding_rate": 0.0001,
            "funding_annualized_simple_pct": 10.95,
            "funding_interval_hours": 8,
        }])
        item = result["perpetual"][0]
        self.assertEqual(item["status"], "OK")
        self.assertNotIn("days_to_maturity", item)
        self.assertNotIn("annualized_basis_pct", item)
        self.assertEqual(result["delivery"], [])

    def test_contract_type_mismatch_is_rejected(self):
        result = self.build([{
            "contract_symbol": "BTCUSDT",
            "contract_type": "CURRENT_QUARTER",
            "contract_status": "TRADING",
        }])
        item = result["perpetual"][0]
        self.assertEqual(item["status"], "REJECTED")
        self.assertEqual(item["reason"], "CONTRACT_TYPE_MISMATCH")

    def test_delivery_requires_positive_dte_and_computes_delta(self):
        watchlist = {
            "schema_version": "carry-watchlist.v1",
            "id": "delivery",
            "version": "1.0.0",
            "entries": [{
                "id": "btc-quarter",
                "spot_symbol": "BTCUSDT",
                "futures_symbol": "BTCUSDT_260925",
                "expected_contract_type": "CURRENT_QUARTER",
                "enabled": True,
                "thresholds": {"annualized_basis_pct": 8.0},
            }],
        }
        previous = {
            "delivery": [{
                "watch_id": "btc-quarter",
                "annualized_basis_pct": 6.0,
                "days_to_maturity": 50.0,
            }]
        }
        result = self.build([{
            "contract_symbol": "BTCUSDT_260925",
            "contract_type": "CURRENT_QUARTER",
            "contract_status": "TRADING",
            "delivery_datetime": "2026-09-25T08:00:00Z",
            "days_to_maturity": 46.0,
            "spot_price": 100.0,
            "futures_price": 101.0,
            "basis_percent": 1.0,
            "annualized_basis": 7.9348,
            "annualization_method": "simple_actual_dte_365",
            "annualization_day_count": 365.0,
        }], previous=previous, watchlist=watchlist)
        item = result["delivery"][0]
        self.assertEqual(item["status"], "OK")
        self.assertAlmostEqual(item["change"]["basis_pct"], 1.9348)
        self.assertEqual(item["change"]["days_to_maturity"], -4.0)

    def test_non_positive_dte_is_rejected(self):
        watchlist = {
            "schema_version": "carry-watchlist.v1",
            "id": "delivery",
            "version": "1.0.0",
            "entries": [{
                "id": "expired",
                "spot_symbol": "BTCUSDT",
                "futures_symbol": "BTCUSDT_OLD",
                "expected_contract_type": "CURRENT_QUARTER",
                "enabled": True,
                "thresholds": {},
            }],
        }
        result = self.build([{
            "contract_symbol": "BTCUSDT_OLD",
            "contract_type": "CURRENT_QUARTER",
            "delivery_datetime": "2026-08-01T00:00:00Z",
            "days_to_maturity": 0,
        }], watchlist=watchlist)
        self.assertEqual(result["delivery"][0]["reason"], "DTE_NON_POSITIVE_OR_MISSING")

    def test_credentials_are_forbidden(self):
        watchlist = dict(BASE_WATCHLIST)
        watchlist["api_key"] = "do-not-store"
        with self.assertRaisesRegex(ValueError, "credential-like"):
            validate_watchlist(watchlist)


if __name__ == "__main__":
    unittest.main()

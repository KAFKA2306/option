import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from src.collect_market_structure import (
    active_contracts,
    contract_snapshot,
    daily_rows,
    update_metadata_history,
)


class MarketStructureCollectorTest(unittest.TestCase):
    def test_unknown_active_contract_type_fails_closed(self):
        exchange = {
            "symbols": [
                {
                    "symbol": "BTCUSDT_WEIRD",
                    "pair": "BTCUSDT",
                    "status": "TRADING",
                    "contractType": "WEIRD",
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "unsupported active BTC contract type"):
            active_contracts(exchange)

    def test_perpetual_and_delivery_metrics_are_separate(self):
        day_ms = 1_767_225_600_000
        close_ms = day_ms + 86_399_999
        payloads = {
            "spot_klines": [[day_ms, "0", "0", "0", "100", "1", close_ms, "100"]],
            "index_klines": [[day_ms, "0", "0", "0", "100", "1", close_ms, "100"]],
            "funding": [
                {
                    "symbol": "BTCUSDT",
                    "fundingTime": day_ms + 1,
                    "fundingRate": "0.0001",
                    "markPrice": "101",
                }
            ],
            "contract:BTCUSDT:klines": [[day_ms, "0", "0", "0", "101", "2", close_ms, "202"]],
            "contract:BTCUSDT:mark": [[day_ms, "0", "0", "0", "100.5", "2", close_ms, "201"]],
            "contract:BTCUSDT_260327:klines": [[day_ms, "0", "0", "0", "102", "2", close_ms, "204"]],
            "contract:BTCUSDT_260327:mark": [[day_ms, "0", "0", "0", "101.5", "2", close_ms, "203"]],
        }
        contracts = [
            {
                "symbol": "BTCUSDT",
                "pair": "BTCUSDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
                "deliveryDate": 0,
            },
            {
                "symbol": "BTCUSDT_260327",
                "pair": "BTCUSDT",
                "status": "TRADING",
                "contractType": "CURRENT_QUARTER",
                "deliveryDate": 1_774_569_600_000,
            },
        ]
        rows = daily_rows(payloads, contracts)
        perp = next(row for row in rows if row["contract_type"] == "PERPETUAL")
        delivery = next(row for row in rows if row["contract_type"] == "CURRENT_QUARTER")
        self.assertIsNotNone(perp["perpetual_premium_pct"])
        self.assertIsNone(perp["delivery_basis_pct"])
        self.assertEqual(perp["funding_event_count"], 1)
        self.assertIsNone(delivery["perpetual_premium_pct"])
        self.assertIsNotNone(delivery["delivery_basis_pct"])
        self.assertIsNotNone(delivery["annualized_delivery_basis_pct"])
        self.assertIsNone(delivery["funding_rate_sum"])

    def test_metadata_history_only_appends_on_change(self):
        contracts = [
            {
                "symbol": "BTCUSDT",
                "pair": "BTCUSDT",
                "status": "TRADING",
                "contractType": "PERPETUAL",
                "deliveryDate": 0,
            }
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = update_metadata_history(root, contracts, "2026-01-01T00:00:00+00:00")
            second = update_metadata_history(root, contracts, "2026-01-02T00:00:00+00:00")
            changed = contracts + [
                {
                    "symbol": "BTCUSDT_260327",
                    "pair": "BTCUSDT",
                    "status": "TRADING",
                    "contractType": "CURRENT_QUARTER",
                    "deliveryDate": 1,
                }
            ]
            third = update_metadata_history(root, changed, "2026-01-03T00:00:00+00:00")
        self.assertEqual(len(first["changes"]), 1)
        self.assertEqual(len(second["changes"]), 1)
        self.assertEqual(len(third["changes"]), 2)

    def test_expired_delivery_contract_rejected(self):
        payloads = iter(
            [
                (
                    {
                        "markPrice": "101",
                        "indexPrice": "100",
                        "lastFundingRate": "",
                        "nextFundingTime": 0,
                    },
                    b"p",
                    "premium",
                ),
                ({"openInterest": "2"}, b"o", "oi"),
                ({"volume": "3", "quoteVolume": "300"}, b"t", "ticker"),
                ({"bids": [["100", "1"]], "asks": [["102", "1"]]}, b"d", "depth"),
            ]
        )
        meta = {
            "symbol": "BTCUSDT_TEST",
            "pair": "BTCUSDT",
            "contractType": "CURRENT_QUARTER",
            "status": "TRADING",
            "deliveryDate": 1,
        }
        with patch(
            "src.collect_market_structure.get_json",
            side_effect=lambda *args, **kwargs: next(payloads),
        ):
            with self.assertRaisesRegex(ValueError, "expired delivery contract"):
                contract_snapshot(meta, 100.0, datetime(2026, 1, 1, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()

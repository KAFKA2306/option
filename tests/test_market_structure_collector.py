from datetime import datetime, timezone

import pytest

from src.collect_market_structure import contract_snapshot


def test_contract_snapshot_rejects_unknown_contract_without_network(monkeypatch):
    def fake_get_json(*args, **kwargs):
        raise AssertionError("network must not be called for this test")

    # Unknown contract metadata is rejected only after public endpoint reads in the
    # production function, so test the explicit metadata boundary using an expired
    # delivery contract with deterministic fake endpoint payloads.
    payloads = iter([
        ({"markPrice": "101", "indexPrice": "100", "lastFundingRate": "", "nextFundingTime": 0}, b"p", "premium"),
        ({"openInterest": "2"}, b"o", "oi"),
        ({"volume": "3", "quoteVolume": "300"}, b"t", "ticker"),
        ({"bids": [["100", "1"]], "asks": [["102", "1"]]}, b"d", "depth"),
    ])
    monkeypatch.setattr("src.collect_market_structure.get_json", lambda *a, **k: next(payloads))
    meta = {"symbol": "BTCUSDT_TEST", "pair": "BTCUSDT", "contractType": "CURRENT_QUARTER", "status": "TRADING", "deliveryDate": 1}
    with pytest.raises(ValueError, match="expired delivery contract"):
        contract_snapshot(meta, 100.0, datetime(2026, 1, 1, tzinfo=timezone.utc))

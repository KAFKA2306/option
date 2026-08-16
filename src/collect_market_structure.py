#!/usr/bin/env python3
"""Collect contract-aware BTC market-structure snapshots from Binance public APIs."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SPOT_BASE = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"


def get_json(base: str, path: str, params: dict[str, object] | None = None) -> tuple[object, bytes, str]:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{base}{path}{query}"
    req = Request(url, headers={"User-Agent": "bitcoin-derivatives/1.0"})
    with urlopen(req, timeout=30) as response:
        raw = response.read()
    return json.loads(raw), raw, url


def contract_snapshot(symbol_meta: dict[str, object], spot_price: float, observed_at: datetime) -> dict[str, object]:
    symbol = str(symbol_meta["symbol"])
    premium, premium_raw, premium_url = get_json(FUTURES_BASE, "/fapi/v1/premiumIndex", {"symbol": symbol})
    oi, oi_raw, oi_url = get_json(FUTURES_BASE, "/fapi/v1/openInterest", {"symbol": symbol})
    stats, stats_raw, stats_url = get_json(FUTURES_BASE, "/fapi/v1/ticker/24hr", {"symbol": symbol})
    depth, depth_raw, depth_url = get_json(FUTURES_BASE, "/fapi/v1/depth", {"symbol": symbol, "limit": 5})

    futures_price = float(premium["markPrice"])
    contract_type = str(symbol_meta.get("contractType") or "")
    delivery_ms = int(symbol_meta.get("deliveryDate") or 0)
    result: dict[str, object] = {
        "symbol": symbol,
        "pair": symbol_meta.get("pair"),
        "contract_type": contract_type,
        "status": symbol_meta.get("status"),
        "onboard_date_ms": symbol_meta.get("onboardDate"),
        "delivery_date_ms": delivery_ms or None,
        "underlying_type": symbol_meta.get("underlyingType"),
        "spot_price": spot_price,
        "mark_price": futures_price,
        "index_price": float(premium["indexPrice"]),
        "last_funding_rate": float(premium["lastFundingRate"]) if premium.get("lastFundingRate") not in (None, "") else None,
        "next_funding_time_ms": int(premium["nextFundingTime"]) if premium.get("nextFundingTime") else None,
        "open_interest": float(oi["openInterest"]),
        "volume_24h": float(stats["volume"]),
        "quote_volume_24h": float(stats["quoteVolume"]),
        "best_bid": float(depth["bids"][0][0]) if depth.get("bids") else None,
        "best_ask": float(depth["asks"][0][0]) if depth.get("asks") else None,
        "raw_sha256": {
            "premium_index": hashlib.sha256(premium_raw).hexdigest(),
            "open_interest": hashlib.sha256(oi_raw).hexdigest(),
            "ticker_24h": hashlib.sha256(stats_raw).hexdigest(),
            "depth": hashlib.sha256(depth_raw).hexdigest(),
        },
        "source_urls": [premium_url, oi_url, stats_url, depth_url],
    }
    result["raw_price_gap_pct"] = (futures_price / spot_price - 1.0) * 100.0

    if contract_type == "PERPETUAL":
        result["perpetual_premium_pct"] = result["raw_price_gap_pct"]
        result["days_to_maturity"] = None
        result["annualized_basis_pct"] = None
    elif delivery_ms > 0:
        delivery = datetime.fromtimestamp(delivery_ms / 1000, tz=timezone.utc)
        dte = (delivery - observed_at).total_seconds() / 86400
        if dte <= 0:
            raise ValueError(f"expired delivery contract returned as active: {symbol}")
        result["perpetual_premium_pct"] = None
        result["days_to_maturity"] = dte
        result["annualized_basis_pct"] = result["raw_price_gap_pct"] * 365.0 / dte
    else:
        raise ValueError(f"unsupported contract metadata: {symbol} type={contract_type!r}")
    return result


def collect() -> dict[str, object]:
    observed_at = datetime.now(timezone.utc)
    spot, spot_raw, spot_url = get_json(SPOT_BASE, "/api/v3/ticker/bookTicker", {"symbol": "BTCUSDT"})
    exchange, exchange_raw, exchange_url = get_json(FUTURES_BASE, "/fapi/v1/exchangeInfo")
    spot_price = (float(spot["bidPrice"]) + float(spot["askPrice"])) / 2.0

    contracts = []
    for meta in exchange.get("symbols", []):
        if meta.get("pair") != "BTCUSDT" or meta.get("status") != "TRADING":
            continue
        contracts.append(contract_snapshot(meta, spot_price, observed_at))

    if not contracts:
        raise RuntimeError("no active BTCUSDT futures contracts returned")
    return {
        "schema_version": 1,
        "observed_at": observed_at.isoformat(),
        "venue": "Binance",
        "spot": {
            "symbol": "BTCUSDT",
            "bid": float(spot["bidPrice"]),
            "ask": float(spot["askPrice"]),
            "mid": spot_price,
            "source_url": spot_url,
            "raw_sha256": hashlib.sha256(spot_raw).hexdigest(),
        },
        "exchange_info": {"source_url": exchange_url, "raw_sha256": hashlib.sha256(exchange_raw).hexdigest()},
        "contracts": contracts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("output/market-structure"))
    args = parser.parse_args()
    payload = collect()
    stamp = datetime.fromisoformat(str(payload["observed_at"])).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / f"btc-binance-{stamp}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()

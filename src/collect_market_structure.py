#!/usr/bin/env python3
"""Collect and rebuild a contract-aware BTC derivatives dataset from Binance public APIs."""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SPOT_BASE = "https://data-api.binance.vision"
FUTURES_BASE = "https://www.binance.com"
PAIR = "BTCUSDT"
SUPPORTED = {"PERPETUAL", "CURRENT_MONTH", "NEXT_MONTH", "CURRENT_QUARTER", "NEXT_QUARTER"}
OI_NOTE = "Binance Open Interest Statistics exposes only the latest 1 month."


def dump(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def get_json(base: str, path: str, params: dict[str, object] | None = None) -> tuple[object, bytes, str]:
    query = f"?{urlencode(params)}" if params else ""
    url = f"{base}{path}{query}"
    req = Request(url, headers={"User-Agent": "KAFKA2306/bitcoin-derivatives"})
    with urlopen(req, timeout=60) as response:
        raw = response.read()
    if not raw:
        raise RuntimeError(f"empty Binance response: {url}")
    return json.loads(raw), raw, url


def capture(evidence: dict[str, Any], payloads: dict[str, Any], root: Path, key: str,
            base: str, path: str, params: dict[str, object] | None = None) -> Any:
    payload, raw, url = get_json(base, path, params)
    sha = digest(raw)
    dst = root / "raw" / "objects" / f"{sha}.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        dst.write_bytes(raw)
    evidence[key] = {"source_url": url, "sha256": sha, "path": dst.as_posix()}
    payloads[key] = payload
    return payload


def active_contracts(exchange: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for meta in exchange.get("symbols", []):
        if meta.get("pair") != PAIR or meta.get("status") != "TRADING":
            continue
        contract_type = str(meta.get("contractType") or "")
        if contract_type not in SUPPORTED:
            raise ValueError(f"unsupported active BTC contract type: {meta.get('symbol')} {contract_type!r}")
        out.append(meta)
    if not out:
        raise RuntimeError("no active BTCUSDT futures contracts returned")
    if sum(str(row["contractType"]) == "PERPETUAL" for row in out) != 1:
        raise RuntimeError("expected exactly one active BTCUSDT perpetual contract")
    return sorted(out, key=lambda row: (str(row["contractType"]), str(row["symbol"])))


def collect(root: Path, lookback_days: int) -> tuple[dict[str, Any], dict[str, Any]]:
    now = datetime.now(UTC)
    start_ms = int((now - timedelta(days=lookback_days)).timestamp() * 1000)
    oi_start_ms = int((now - timedelta(days=29)).timestamp() * 1000)
    evidence: dict[str, Any] = {}
    payloads: dict[str, Any] = {}
    exchange = capture(evidence, payloads, root, "exchange", FUTURES_BASE, "/fapi/v1/exchangeInfo")
    contracts = active_contracts(exchange)
    perpetual = next(row for row in contracts if row["contractType"] == "PERPETUAL")
    capture(evidence, payloads, root, "spot_book", SPOT_BASE, "/api/v3/ticker/bookTicker", {"symbol": PAIR})
    capture(evidence, payloads, root, "spot_klines", SPOT_BASE, "/api/v3/klines",
            {"symbol": PAIR, "interval": "1d", "startTime": start_ms, "limit": 200})
    capture(evidence, payloads, root, "index_klines", FUTURES_BASE, "/fapi/v1/indexPriceKlines",
            {"pair": PAIR, "interval": "1d", "startTime": start_ms, "limit": 200})
    capture(evidence, payloads, root, "funding", FUTURES_BASE, "/fapi/v1/fundingRate",
            {"symbol": perpetual["symbol"], "startTime": start_ms, "limit": 1000})
    capture(evidence, payloads, root, "oi_history", FUTURES_BASE, "/futures/data/openInterestHist",
            {"symbol": perpetual["symbol"], "period": "1d", "startTime": oi_start_ms, "limit": 500})
    for meta in contracts:
        symbol = str(meta["symbol"])
        prefix = f"contract:{symbol}"
        capture(evidence, payloads, root, f"{prefix}:premium", FUTURES_BASE, "/fapi/v1/premiumIndex", {"symbol": symbol})
        capture(evidence, payloads, root, f"{prefix}:oi", FUTURES_BASE, "/fapi/v1/openInterest", {"symbol": symbol})
        capture(evidence, payloads, root, f"{prefix}:ticker", FUTURES_BASE, "/fapi/v1/ticker/24hr", {"symbol": symbol})
        capture(evidence, payloads, root, f"{prefix}:depth", FUTURES_BASE, "/fapi/v1/depth", {"symbol": symbol, "limit": 5})
        contract_start = max(start_ms, int(meta.get("onboardDate") or 0))
        common = {"symbol": symbol, "interval": "1d", "startTime": contract_start, "limit": 200}
        capture(evidence, payloads, root, f"{prefix}:klines", FUTURES_BASE, "/fapi/v1/klines", common)
        capture(evidence, payloads, root, f"{prefix}:mark", FUTURES_BASE, "/fapi/v1/markPriceKlines", common)
    manifest = {
        "schema_version": 1,
        "retrieved_at": now.isoformat(),
        "venue": "Binance",
        "pair": PAIR,
        "lookback_days_requested": lookback_days,
        "evidence": evidence,
    }
    raw_root = root / "raw"
    raw_root.mkdir(parents=True, exist_ok=True)
    raw = dump(manifest)
    sha = digest(raw)
    manifest_path = raw_root / "manifests" / f"{sha}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    if not manifest_path.exists():
        manifest_path.write_bytes(raw)
    (raw_root / "latest-manifest.json").write_bytes(raw)
    return manifest, payloads


def load(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest = json.loads((root / "raw" / "latest-manifest.json").read_text())
    payloads: dict[str, Any] = {}
    for key, item in manifest["evidence"].items():
        path = Path(item["path"])
        raw = path.read_bytes()
        if digest(raw) != item["sha256"]:
            raise ValueError(f"raw evidence hash mismatch: {key}")
        payloads[key] = json.loads(raw)
    return manifest, payloads


def klines(rows: list[list[Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if len(row) < 8:
            raise ValueError("unexpected kline schema")
        date = datetime.fromtimestamp(int(row[0]) / 1000, UTC).date().isoformat()
        out[date] = {
            "close_time_ms": int(row[6]), "close": float(row[4]),
            "volume": float(row[5]), "quote_volume": float(row[7]),
        }
    return out


def funding_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not {"symbol", "fundingTime", "fundingRate"} <= set(row):
            raise ValueError("unexpected funding schema")
        ms = int(row["fundingTime"])
        out.append({
            "symbol": str(row["symbol"]), "funding_time_ms": ms,
            "funding_time": datetime.fromtimestamp(ms / 1000, UTC).isoformat(),
            "funding_rate": float(row["fundingRate"]),
            "mark_price": float(row["markPrice"]) if row.get("markPrice") not in (None, "") else None,
        })
    return sorted(out, key=lambda row: row["funding_time_ms"])


def oi_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        if not {"symbol", "sumOpenInterest", "sumOpenInterestValue", "timestamp"} <= set(row):
            raise ValueError("unexpected open-interest schema")
        ms = int(row["timestamp"])
        out.append({
            "symbol": str(row["symbol"]), "timestamp_ms": ms,
            "timestamp": datetime.fromtimestamp(ms / 1000, UTC).isoformat(),
            "open_interest": float(row["sumOpenInterest"]),
            "open_interest_value": float(row["sumOpenInterestValue"]),
        })
    return sorted(out, key=lambda row: row["timestamp_ms"])


def metadata_snapshot(contracts: list[dict[str, Any]], observed_at: str) -> dict[str, Any]:
    normalized = [{
        "symbol": row["symbol"], "pair": row.get("pair"), "contract_type": row.get("contractType"),
        "status": row.get("status"), "onboard_date_ms": row.get("onboardDate"),
        "delivery_date_ms": row.get("deliveryDate"), "underlying_type": row.get("underlyingType"),
    } for row in contracts]
    return {"observed_at": observed_at, "metadata_sha256": digest(dump(normalized)), "contracts": normalized}


def update_metadata_history(root: Path, contracts: list[dict[str, Any]], observed_at: str) -> dict[str, Any]:
    path = root / "metadata-history.json"
    history = json.loads(path.read_text()) if path.exists() else {"schema_version": 1, "changes": []}
    snap = metadata_snapshot(contracts, observed_at)
    if not history["changes"] or history["changes"][-1]["metadata_sha256"] != snap["metadata_sha256"]:
        history["changes"].append(snap)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump(history))
    return history


def current_terms(payloads: dict[str, Any], contracts: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    spot = payloads["spot_book"]
    spot_mid = (float(spot["bidPrice"]) + float(spot["askPrice"])) / 2
    out = []
    for meta in contracts:
        symbol, contract_type = str(meta["symbol"]), str(meta["contractType"])
        prefix = f"contract:{symbol}"
        premium, oi, ticker, depth = (payloads[f"{prefix}:premium"], payloads[f"{prefix}:oi"],
                                      payloads[f"{prefix}:ticker"], payloads[f"{prefix}:depth"])
        last, mark, index = float(ticker["lastPrice"]), float(premium["markPrice"]), float(premium["indexPrice"])
        gap = (last / spot_mid - 1) * 100
        item = {
            "observed_at": now.isoformat(), "symbol": symbol, "contract_type": contract_type,
            "status": meta.get("status"), "onboard_date_ms": meta.get("onboardDate"),
            "delivery_date_ms": meta.get("deliveryDate"), "spot_mid": spot_mid,
            "contract_last_price": last, "mark_price": mark, "index_price": index,
            "mark_index_premium_pct": (mark / index - 1) * 100, "raw_price_gap_pct": gap,
            "open_interest": float(oi["openInterest"]), "volume_24h": float(ticker["volume"]),
            "quote_volume_24h": float(ticker["quoteVolume"]),
            "best_bid": float(depth["bids"][0][0]) if depth.get("bids") else None,
            "best_ask": float(depth["asks"][0][0]) if depth.get("asks") else None,
        }
        if contract_type == "PERPETUAL":
            item.update({
                "perpetual_premium_pct": gap,
                "last_funding_rate": float(premium["lastFundingRate"]) if premium.get("lastFundingRate") not in (None, "") else None,
                "next_funding_time_ms": int(premium["nextFundingTime"]) if premium.get("nextFundingTime") else None,
                "days_to_maturity": None, "delivery_basis_pct": None, "annualized_delivery_basis_pct": None,
            })
        else:
            delivery_ms = int(meta.get("deliveryDate") or 0)
            if delivery_ms <= 0:
                raise ValueError(f"delivery contract lacks deliveryDate: {symbol}")
            dte = (datetime.fromtimestamp(delivery_ms / 1000, UTC) - now).total_seconds() / 86400
            if dte <= 0:
                raise ValueError(f"expired delivery contract returned as TRADING: {symbol}")
            item.update({
                "perpetual_premium_pct": None, "last_funding_rate": None, "next_funding_time_ms": None,
                "days_to_maturity": dte, "delivery_basis_pct": gap,
                "annualized_delivery_basis_pct": gap * 365 / dte,
            })
        out.append(item)
    return out


def daily_rows(payloads: dict[str, Any], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    spot, index = klines(payloads["spot_klines"]), klines(payloads["index_klines"])
    funding = funding_rows(payloads["funding"])
    by_day: dict[str, list[dict[str, Any]]] = {}
    for event in funding:
        by_day.setdefault(event["funding_time"][:10], []).append(event)
    out = []
    for meta in contracts:
        symbol, contract_type = str(meta["symbol"]), str(meta["contractType"])
        prefix = f"contract:{symbol}"
        futures, mark = klines(payloads[f"{prefix}:klines"]), klines(payloads[f"{prefix}:mark"])
        for date in sorted(set(spot) & set(index) & set(futures) & set(mark)):
            s, i, f, m = spot[date], index[date], futures[date], mark[date]
            gap = (f["close"] / s["close"] - 1) * 100
            row = {
                "date": date, "symbol": symbol, "contract_type": contract_type,
                "spot_close": s["close"], "contract_close": f["close"], "mark_close": m["close"],
                "index_close": i["close"], "volume": f["volume"], "quote_volume": f["quote_volume"],
                "mark_index_premium_pct": (m["close"] / i["close"] - 1) * 100,
                "raw_price_gap_pct": gap,
            }
            if contract_type == "PERPETUAL":
                events = by_day.get(date, [])
                row.update({
                    "perpetual_premium_pct": gap, "funding_event_count": len(events),
                    "funding_rate_sum": sum(e["funding_rate"] for e in events) if events else None,
                    "days_to_maturity": None, "delivery_basis_pct": None, "annualized_delivery_basis_pct": None,
                })
            else:
                delivery_ms = int(meta.get("deliveryDate") or 0)
                if delivery_ms <= 0:
                    raise ValueError(f"delivery contract lacks deliveryDate: {symbol}")
                dte = (delivery_ms - f["close_time_ms"]) / 86_400_000
                if dte <= 0:
                    continue
                row.update({
                    "perpetual_premium_pct": None, "funding_event_count": None, "funding_rate_sum": None,
                    "days_to_maturity": dte, "delivery_basis_pct": gap,
                    "annualized_delivery_basis_pct": gap * 365 / dte,
                })
            out.append(row)
    return sorted(out, key=lambda row: (row["date"], row["symbol"]))


def build(manifest: dict[str, Any], payloads: dict[str, Any], root: Path, api_dir: Path,
          update_history: bool = True) -> dict[str, Any]:
    contracts = active_contracts(payloads["exchange"])
    now = datetime.fromisoformat(str(manifest["retrieved_at"]).replace("Z", "+00:00")).astimezone(UTC)
    daily = daily_rows(payloads, contracts)
    funding = funding_rows(payloads["funding"])
    oi = oi_rows(payloads["oi_history"])
    term = current_terms(payloads, contracts, now)
    perp_dates = sorted({row["date"] for row in daily if row["contract_type"] == "PERPETUAL"})
    delivery_dates = sorted({row["date"] for row in daily if row["contract_type"] != "PERPETUAL"})
    if not perp_dates:
        raise RuntimeError("no perpetual daily observations built")
    api_dir.mkdir(parents=True, exist_ok=True)
    (api_dir / "daily.json").write_bytes(dump({"schema_version": 1, "records": daily}))
    (api_dir / "funding.json").write_bytes(dump({"schema_version": 1, "events": funding}))
    (api_dir / "open-interest.json").write_bytes(dump({"schema_version": 1, "retention_note": OI_NOTE, "records": oi}))
    (api_dir / "term-structure.json").write_bytes(dump({"schema_version": 1, "contracts": term}))
    (api_dir / "current.json").write_bytes(dump({"schema_version": 1, "observed_at": now.isoformat(), "spot": payloads["spot_book"], "contracts": term}))
    history = update_metadata_history(root, contracts, now.isoformat()) if update_history else ({"schema_version": 1, "changes": []})
    coverage = {
        "perpetual_first_date": perp_dates[0], "perpetual_last_date": perp_dates[-1], "perpetual_day_count": len(perp_dates),
        "delivery_first_date": delivery_dates[0] if delivery_dates else None,
        "delivery_last_date": delivery_dates[-1] if delivery_dates else None,
        "delivery_day_count": len(delivery_dates), "funding_event_count": len(funding),
        "funding_first_time": funding[0]["funding_time"] if funding else None,
        "funding_last_time": funding[-1]["funding_time"] if funding else None,
        "open_interest_observation_count": len(oi), "open_interest_first_time": oi[0]["timestamp"] if oi else None,
        "open_interest_last_time": oi[-1]["timestamp"] if oi else None,
        "active_contract_count": len(contracts),
        "active_delivery_contract_count": sum(row["contract_type"] != "PERPETUAL" for row in term),
        "metadata_change_count": len(history.get("changes", [])), "raw_evidence_count": len(manifest["evidence"]),
    }
    index = {
        "schema_version": 1, "dataset": "BTC Binance derivatives market structure", "venue": "Binance", "pair": PAIR,
        "retrieved_at": now.isoformat(), "coverage": coverage,
        "views": {"current": "current.json", "daily": "daily.json", "funding": "funding.json",
                  "open_interest": "open-interest.json", "term_structure": "term-structure.json",
                  "metadata_history": "../../../data/derivatives/metadata-history.json",
                  "raw_manifest": "../../../data/derivatives/raw/latest-manifest.json"},
        "rules": ["PERPETUAL premium/funding and delivery basis are different metrics.",
                  "days_to_maturity and annualized_delivery_basis_pct exist only for delivery contracts.",
                  "unknown active contract types fail closed.",
                  "raw endpoint bytes are content-addressed by SHA-256 before derived views are written.", OI_NOTE],
    }
    (api_dir / "index.json").write_bytes(dump(index))
    return index


def contract_snapshot(symbol_meta: dict[str, object], spot_price: float, observed_at: datetime) -> dict[str, object]:
    """Backward-compatible current snapshot used by existing tests and callers."""
    symbol = str(symbol_meta["symbol"])
    contract_type = str(symbol_meta.get("contractType") or "")
    if contract_type not in SUPPORTED:
        raise ValueError(f"unsupported contract metadata: {symbol} type={contract_type!r}")
    premium, premium_raw, premium_url = get_json(FUTURES_BASE, "/fapi/v1/premiumIndex", {"symbol": symbol})
    oi, oi_raw, oi_url = get_json(FUTURES_BASE, "/fapi/v1/openInterest", {"symbol": symbol})
    stats, stats_raw, stats_url = get_json(FUTURES_BASE, "/fapi/v1/ticker/24hr", {"symbol": symbol})
    depth, depth_raw, depth_url = get_json(FUTURES_BASE, "/fapi/v1/depth", {"symbol": symbol, "limit": 5})
    mark = float(premium["markPrice"])
    result: dict[str, object] = {
        "symbol": symbol, "pair": symbol_meta.get("pair"), "contract_type": contract_type,
        "status": symbol_meta.get("status"), "onboard_date_ms": symbol_meta.get("onboardDate"),
        "delivery_date_ms": symbol_meta.get("deliveryDate") or None, "underlying_type": symbol_meta.get("underlyingType"),
        "spot_price": spot_price, "mark_price": mark, "index_price": float(premium["indexPrice"]),
        "last_funding_rate": float(premium["lastFundingRate"]) if premium.get("lastFundingRate") not in (None, "") else None,
        "next_funding_time_ms": int(premium["nextFundingTime"]) if premium.get("nextFundingTime") else None,
        "open_interest": float(oi["openInterest"]), "volume_24h": float(stats["volume"]),
        "quote_volume_24h": float(stats["quoteVolume"]),
        "best_bid": float(depth["bids"][0][0]) if depth.get("bids") else None,
        "best_ask": float(depth["asks"][0][0]) if depth.get("asks") else None,
        "raw_sha256": {"premium_index": digest(premium_raw), "open_interest": digest(oi_raw),
                       "ticker_24h": digest(stats_raw), "depth": digest(depth_raw)},
        "source_urls": [premium_url, oi_url, stats_url, depth_url],
    }
    gap = (mark / spot_price - 1) * 100
    result["raw_price_gap_pct"] = gap
    if contract_type == "PERPETUAL":
        result.update({"perpetual_premium_pct": gap, "days_to_maturity": None, "annualized_basis_pct": None})
    else:
        delivery_ms = int(symbol_meta.get("deliveryDate") or 0)
        delivery = datetime.fromtimestamp(delivery_ms / 1000, UTC) if delivery_ms else None
        dte = (delivery - observed_at).total_seconds() / 86400 if delivery else -1
        if dte <= 0:
            raise ValueError(f"expired delivery contract returned as active: {symbol}")
        result.update({"perpetual_premium_pct": None, "days_to_maturity": dte, "annualized_basis_pct": gap * 365 / dte})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("data/derivatives"))
    parser.add_argument("--api-dir", type=Path, default=Path("api/v1/bitcoin-derivatives"))
    parser.add_argument("--lookback-days", type=int, default=100)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--no-history-update", action="store_true")
    args = parser.parse_args()
    if args.lookback_days < 90:
        raise ValueError("lookback-days must be at least 90")
    manifest, payloads = load(args.data_root) if args.offline else collect(args.data_root, args.lookback_days)
    index = build(manifest, payloads, args.data_root, args.api_dir, update_history=not args.no_history_update)
    print(json.dumps(index["coverage"], sort_keys=True))


if __name__ == "__main__":
    main()

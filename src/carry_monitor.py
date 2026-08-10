from __future__ import annotations

import argparse
import html
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

SCHEMA_VERSION = "carry-monitor.v1"
WATCHLIST_VERSION = "carry-watchlist.v1"
PERPETUAL_TYPES = {"PERPETUAL", "PERPETUAL_DELIVERING"}
DELIVERY_TYPES = {"CURRENT_MONTH", "NEXT_MONTH", "CURRENT_QUARTER", "NEXT_QUARTER"}
FORBIDDEN_KEY_PARTS = ("api_key", "apikey", "secret", "token", "password", "credential")


def _is_finite(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _walk_forbidden_keys(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(part in normalized for part in FORBIDDEN_KEY_PARTS):
                raise ValueError(f"credential-like field is forbidden: {path}{key}")
            _walk_forbidden_keys(child, f"{path}{key}.")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden_keys(child, f"{path}{index}.")


def validate_watchlist(watchlist: dict[str, Any]) -> None:
    if watchlist.get("schema_version") != WATCHLIST_VERSION:
        raise ValueError(f"watchlist schema_version must be {WATCHLIST_VERSION}")
    _walk_forbidden_keys(watchlist)
    entries = watchlist.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("watchlist entries must be a non-empty list")
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("watchlist entry must be an object")
        for field in ("id", "spot_symbol", "futures_symbol", "expected_contract_type", "enabled"):
            if field not in entry:
                raise ValueError(f"watchlist entry missing {field}")
        entry_id = str(entry["id"]).strip()
        if not entry_id or entry_id in seen:
            raise ValueError(f"invalid or duplicate watchlist id: {entry_id!r}")
        seen.add(entry_id)
        contract_type = str(entry["expected_contract_type"]).upper()
        if contract_type not in PERPETUAL_TYPES | DELIVERY_TYPES:
            raise ValueError(f"{entry_id}: unsupported expected_contract_type {contract_type!r}")
        thresholds = entry.get("thresholds", {})
        if thresholds is not None and not isinstance(thresholds, dict):
            raise ValueError(f"{entry_id}: thresholds must be an object")


def _threshold_state(value: Any, threshold: Any) -> str:
    if threshold is None:
        return "NOT_CONFIGURED"
    if not _is_finite(value):
        return "NOT_COMPUTABLE"
    if not _is_finite(threshold):
        raise ValueError("threshold must be finite when configured")
    return "TRIGGERED" if abs(float(value)) >= abs(float(threshold)) else "NORMAL"


def _previous_index(previous: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not previous:
        return {}
    result = {}
    for section in ("perpetual", "delivery"):
        for entry in previous.get(section, []) or []:
            if isinstance(entry, dict) and entry.get("watch_id"):
                result[str(entry["watch_id"])] = entry
    return result


def _delta(current: Any, prior: Any) -> float | None:
    if not (_is_finite(current) and _is_finite(prior)):
        return None
    return float(current) - float(prior)


def _rejected(entry: dict[str, Any], row: dict[str, Any], reason: str, provenance: dict[str, Any]) -> dict[str, Any]:
    return {
        "watch_id": entry["id"],
        "spot_symbol": entry["spot_symbol"],
        "futures_symbol": entry["futures_symbol"],
        "contract_type": row.get("contract_type"),
        "status": "REJECTED",
        "reason": reason,
        "provenance": provenance,
    }


def build_monitor(
    rows: list[dict[str, Any]],
    watchlist: dict[str, Any],
    *,
    retrieved_at: str,
    commit_sha: str,
    source_endpoint: str,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_watchlist(watchlist)
    if not retrieved_at or not commit_sha or not source_endpoint:
        raise ValueError("retrieved_at, commit_sha, and source_endpoint are required provenance")
    _walk_forbidden_keys(rows)

    row_by_symbol = {}
    for row in rows:
        symbol = str(row.get("contract_symbol") or "").upper()
        if symbol:
            row_by_symbol[symbol] = row

    prior = _previous_index(previous)
    monitor: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "watchlist_id": watchlist.get("id"),
        "watchlist_version": watchlist.get("version"),
        "retrieved_at": retrieved_at,
        "commit_sha": commit_sha,
        "sections": ["perpetual", "delivery"],
        "perpetual": [],
        "delivery": [],
    }

    for watch in watchlist["entries"]:
        if watch["enabled"] is not True:
            continue
        symbol = str(watch["futures_symbol"]).upper()
        row = row_by_symbol.get(symbol)
        provenance = {
            "source_endpoint": source_endpoint,
            "source_symbol": symbol,
            "retrieved_at": retrieved_at,
            "commit_sha": commit_sha,
            "calculation_revision": "contract-aware-v1",
        }
        expected = str(watch["expected_contract_type"]).upper()
        section = "perpetual" if expected in PERPETUAL_TYPES else "delivery"
        if row is None:
            monitor[section].append(_rejected(watch, {}, "SOURCE_SYMBOL_MISSING", provenance))
            continue

        actual = str(row.get("contract_type") or "").upper()
        provenance["contract_metadata"] = {
            "contract_type": actual or None,
            "contract_status": row.get("contract_status"),
            "delivery_datetime": row.get("delivery_datetime"),
        }
        if not actual:
            monitor[section].append(_rejected(watch, row, "CONTRACT_TYPE_MISSING", provenance))
            continue
        if actual != expected:
            monitor[section].append(_rejected(watch, row, "CONTRACT_TYPE_MISMATCH", provenance))
            continue

        previous_entry = prior.get(str(watch["id"]), {})
        thresholds = watch.get("thresholds") or {}

        if actual in PERPETUAL_TYPES:
            premium = row.get("perpetual_premium_pct")
            funding = row.get("funding_rate")
            funding_annualized = row.get("funding_annualized_simple_pct")
            monitor["perpetual"].append({
                "watch_id": watch["id"],
                "spot_symbol": watch["spot_symbol"],
                "futures_symbol": watch["futures_symbol"],
                "contract_type": actual,
                "status": "OK" if _is_finite(premium) else "NOT_COMPUTABLE",
                "reason": None if _is_finite(premium) else "PREMIUM_MISSING",
                "spot_price": row.get("spot_price"),
                "futures_price": row.get("futures_price"),
                "perpetual_premium_pct": premium if _is_finite(premium) else None,
                "funding_rate": funding if _is_finite(funding) else None,
                "funding_annualized_simple_pct": funding_annualized if _is_finite(funding_annualized) else None,
                "funding_time": row.get("funding_time"),
                "funding_interval_hours": row.get("funding_interval_hours") if _is_finite(row.get("funding_interval_hours")) else None,
                "threshold_status": {
                    "premium": _threshold_state(premium, thresholds.get("premium_pct")),
                    "funding": _threshold_state(funding, thresholds.get("funding_rate")),
                },
                "change": {
                    "premium_pct": _delta(premium, previous_entry.get("perpetual_premium_pct")),
                    "funding_rate": _delta(funding, previous_entry.get("funding_rate")),
                },
                "provenance": provenance,
            })
            continue

        dte = row.get("days_to_maturity")
        basis = row.get("basis_percent")
        annualized = row.get("annualized_basis")
        delivery_at = row.get("delivery_datetime")
        if not _is_finite(dte) or float(dte) <= 0:
            monitor["delivery"].append(_rejected(watch, row, "DTE_NON_POSITIVE_OR_MISSING", provenance))
            continue
        if not delivery_at:
            monitor["delivery"].append(_rejected(watch, row, "DELIVERY_DATETIME_MISSING", provenance))
            continue
        monitor["delivery"].append({
            "watch_id": watch["id"],
            "spot_symbol": watch["spot_symbol"],
            "futures_symbol": watch["futures_symbol"],
            "contract_type": actual,
            "status": "OK" if _is_finite(annualized) else "NOT_COMPUTABLE",
            "reason": None if _is_finite(annualized) else "ANNUALIZED_BASIS_MISSING",
            "spot_price": row.get("spot_price"),
            "futures_price": row.get("futures_price"),
            "delivery_datetime": delivery_at,
            "days_to_maturity": float(dte),
            "basis_percent": basis if _is_finite(basis) else None,
            "annualized_basis_pct": annualized if _is_finite(annualized) else None,
            "annualization_method": row.get("annualization_method"),
            "annualization_day_count": row.get("annualization_day_count"),
            "threshold_status": {"basis": _threshold_state(annualized, thresholds.get("annualized_basis_pct"))},
            "change": {
                "basis_pct": _delta(annualized, previous_entry.get("annualized_basis_pct")),
                "days_to_maturity": _delta(dte, previous_entry.get("days_to_maturity")),
            },
            "provenance": provenance,
        })

    return monitor


def render_html(monitor: dict[str, Any]) -> str:
    def table(section: str) -> str:
        cards = []
        for item in monitor.get(section, []):
            label = f"{item.get('futures_symbol')} · {item.get('status')}"
            metric = (
                f"premium {item.get('perpetual_premium_pct')}% / funding {item.get('funding_rate')}"
                if section == "perpetual"
                else f"basis annualized {item.get('annualized_basis_pct')}% / DTE {item.get('days_to_maturity')}"
            )
            cards.append("<article><h3>" + html.escape(label) + "</h3><p>" + html.escape(metric) + "</p><p>" + html.escape(str(item.get("reason") or "validated")) + "</p></article>")
        return "\n".join(cards) or "<p>No enabled contracts.</p>"

    return f"""<!doctype html>
<html lang="ja"><meta charset="utf-8"><title>Funding / Basis Carry Monitor</title>
<body>
<h1>Funding / Basis Carry Monitor</h1>
<p>Observation: {html.escape(str(monitor.get("retrieved_at")))}</p>
<p>This monitor is market-structure evidence, not investment advice, trade execution, or a profit guarantee.</p>
<h2>Perpetual</h2>{table("perpetual")}
<h2>Delivery</h2>{table("delivery")}
</body></html>
"""


def dataframe_latest_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        raise ValueError("analysis parquet is empty")
    latest = frame.sort_index().iloc[-1].to_dict()
    for key, value in list(latest.items()):
        if isinstance(value, pd.Timestamp):
            latest[key] = value.isoformat()
        elif pd.isna(value):
            latest[key] = None
    return [latest]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a fail-closed carry monitor from analyzed parquet data")
    parser.add_argument("--analysis-parquet", required=True)
    parser.add_argument("--watchlist", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-html", required=True)
    parser.add_argument("--retrieved-at", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--source-endpoint", default="Binance USDⓈ-M Futures exchangeInfo/klines/fundingRate")
    parser.add_argument("--previous")
    args = parser.parse_args()

    watchlist = json.loads(Path(args.watchlist).read_text(encoding="utf-8"))
    previous = json.loads(Path(args.previous).read_text(encoding="utf-8")) if args.previous else None
    frame = pd.read_parquet(args.analysis_parquet)
    monitor = build_monitor(
        dataframe_latest_rows(frame),
        watchlist,
        retrieved_at=args.retrieved_at,
        commit_sha=args.commit_sha,
        source_endpoint=args.source_endpoint,
        previous=previous,
    )
    Path(args.output_json).write_text(json.dumps(monitor, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    Path(args.output_html).write_text(render_html(monitor), encoding="utf-8")


if __name__ == "__main__":
    main()

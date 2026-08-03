from __future__ import annotations

import os
from typing import Any

import pandas as pd
from binance.client import Client

from config import create_output_directories
from utils import save_data

api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")
client = Client(api_key, api_secret)


def _klines_to_frame(rows: list[list[Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
            "ignore",
        ],
    )
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True).dt.tz_localize(None)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True).dt.tz_localize(None)
    frame.set_index("open_time", inplace=True)
    numeric = ["open", "high", "low", "close", "volume"]
    frame[numeric] = frame[numeric].astype(float)
    return frame


def fetch_contract_metadata(symbol: str) -> dict[str, Any]:
    exchange_info = client.futures_exchange_info()
    contract = next(
        (
            item
            for item in exchange_info.get("symbols", [])
            if str(item.get("symbol", "")).upper() == symbol.upper()
        ),
        None,
    )
    if contract is None:
        raise RuntimeError(f"Futures contract metadata not found for {symbol}")

    required = {"symbol", "contractType", "status", "onboardDate", "deliveryDate"}
    missing = sorted(key for key in required if contract.get(key) is None)
    if missing:
        raise RuntimeError(f"Futures contract metadata is incomplete for {symbol}: {missing}")
    return {
        "symbol": contract["symbol"],
        "contractType": contract["contractType"],
        "status": contract["status"],
        "onboardDate": int(contract["onboardDate"]),
        "deliveryDate": int(contract["deliveryDate"]),
        "underlyingType": contract.get("underlyingType"),
        "pair": contract.get("pair"),
        "quoteAsset": contract.get("quoteAsset"),
        "marginAsset": contract.get("marginAsset"),
    }


def fetch_funding_history(symbol: str, start_time: pd.Timestamp, end_time: pd.Timestamp) -> pd.DataFrame:
    rows = client.futures_funding_rate(
        symbol=symbol,
        startTime=int(pd.Timestamp(start_time, tz="UTC").timestamp() * 1000),
        endTime=int(pd.Timestamp(end_time, tz="UTC").timestamp() * 1000),
        limit=1000,
    )
    if not rows:
        return pd.DataFrame(columns=["funding_time", "funding_rate", "funding_mark_price"])
    frame = pd.DataFrame(rows)
    frame["funding_time"] = pd.to_datetime(frame["fundingTime"], unit="ms", utc=True).dt.tz_localize(None)
    frame["funding_rate"] = pd.to_numeric(frame["fundingRate"], errors="coerce")
    frame["funding_mark_price"] = pd.to_numeric(frame.get("markPrice"), errors="coerce")
    return frame[["funding_time", "funding_rate", "funding_mark_price"]].drop_duplicates(
        subset=["funding_time"], keep="last"
    ).sort_values("funding_time")


def attach_contract_evidence(
    futures_df: pd.DataFrame,
    metadata: dict[str, Any],
) -> pd.DataFrame:
    frame = futures_df.copy()
    frame.attrs["contract_metadata"] = dict(metadata)
    frame["contract_symbol"] = metadata["symbol"]
    frame["contract_type"] = metadata["contractType"]
    frame["contract_status"] = metadata["status"]
    frame["onboard_datetime"] = pd.to_datetime(metadata["onboardDate"], unit="ms", utc=True)
    frame["delivery_datetime"] = pd.to_datetime(metadata["deliveryDate"], unit="ms", utc=True)
    frame["underlying_type"] = metadata.get("underlyingType")

    if metadata["contractType"] == "PERPETUAL":
        funding = fetch_funding_history(
            metadata["symbol"],
            frame.index.min(),
            frame["close_time"].max(),
        )
        if not funding.empty:
            left = frame.reset_index().sort_values("open_time")
            frame = pd.merge_asof(
                left,
                funding,
                left_on="open_time",
                right_on="funding_time",
                direction="backward",
                allow_exact_matches=True,
            ).set_index("open_time")
            frame.attrs["contract_metadata"] = dict(metadata)
        else:
            frame["funding_time"] = pd.NaT
            frame["funding_rate"] = float("nan")
            frame["funding_mark_price"] = float("nan")
    else:
        frame["funding_time"] = pd.NaT
        frame["funding_rate"] = float("nan")
        frame["funding_mark_price"] = float("nan")
    return frame


def fetch_and_save_data(symbol: str, interval: str, limit: int = 1000):
    create_output_directories()
    try:
        normalized_symbol = symbol.upper()
        spot_klines = client.get_klines(
            symbol=normalized_symbol,
            interval=interval,
            limit=limit,
        )
        spot_df = _klines_to_frame(spot_klines)
        save_data(spot_df, "raw", f"{normalized_symbol.lower()}_spot_prices_{interval}")

        metadata = fetch_contract_metadata(normalized_symbol)
        futures_klines = client.futures_klines(
            symbol=normalized_symbol,
            interval=interval,
            limit=limit,
        )
        futures_df = attach_contract_evidence(
            _klines_to_frame(futures_klines),
            metadata,
        )
        save_data(futures_df, "raw", f"{normalized_symbol.lower()}_futures_prices_{interval}")
        save_data(
            pd.DataFrame([metadata]),
            "raw",
            f"{normalized_symbol.lower()}_contract_metadata",
        )
        return spot_df, futures_df
    except Exception as exc:
        print(f"Error fetching or saving data: {exc}")
        return None, None

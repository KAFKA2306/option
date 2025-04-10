import os
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client
from config import BASE_DIR
from utils import save_data

def get_binance_client():
    """Binance APIクライアントを初期化する関数"""
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        print("エラー: 環境変数 BINANCE_API_KEY および BINANCE_API_SECRET を設定してください。")
        return None
    return Client(api_key, api_secret)

def get_historical_data(months=3, interval=Client.KLINE_INTERVAL_1HOUR):
    """BTCの価格と出来高の日時データを取得する関数"""
    client = get_binance_client()

    if client is None:
        print("Binance APIクライアントの初期化に失敗しました。")
        return None, None

    end_date = datetime.now()
    start_date = end_date - timedelta(days=30 * months)

    start_str = start_date.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_date.strftime("%Y-%m-%d %H:%M:%S")

    try:
        spot_klines = client.get_historical_klines(
            symbol="BTCUSDT",
            interval=interval,
            start_str=start_str,
            end_str=end_str
        )

        futures_klines = client.futures_historical_klines(
            symbol="BTCUSDT",
            interval=interval,
            start_str=start_str,
            end_str=end_str
        )
    except Exception as e:
        print(f"Binance APIからのデータ取得中にエラーが発生しました: {e}")
        return None, None

    spot_df = klines_to_dataframe(spot_klines)
    futures_df = klines_to_dataframe(futures_klines)

    # 異常なタイムスタンプをフィルタリングまたは置換 (オプションだが推奨)
    min_valid_ts = pd.Timestamp("1678-01-01")
    max_valid_ts = pd.Timestamp("2261-12-31")
    spot_df = spot_df[(spot_df['open_time'] >= min_valid_ts) & (spot_df['open_time'] <= max_valid_ts)]
    futures_df = futures_df[(futures_df['open_time'] >= min_valid_ts) & (futures_df['open_time'] <= max_valid_ts)]

    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    save_data(spot_df, "raw", f"btc_spot_prices_{interval_str}")
    save_data(futures_df, "raw", f"btc_futures_prices_{interval_str}")

    return spot_df, futures_df

def klines_to_dataframe(klines):
    """Binance APIから取得したK線データをDataFrameに変換する関数"""
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])

    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', errors='coerce')
    df = df.set_index('open_time')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms', errors='coerce')

    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df = df.dropna() # 不正な値を含む行を削除

    return df
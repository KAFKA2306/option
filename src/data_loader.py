import os
import pandas as pd
from binance.client import Client
from utils import save_data
from config import create_output_directories

# 環境変数からAPIキーを取得
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# クライアントの初期化
client = Client(api_key, api_secret)

def fetch_and_save_data(symbol, interval, limit=1000):
    create_output_directories()
    try:
        # 現物価格データの取得
        spot_klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
        spot_df = pd.DataFrame(spot_klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        spot_df['open_time'] = pd.to_datetime(spot_df['open_time'], unit='ms')
        spot_df['close_time'] = pd.to_datetime(spot_df['close_time'], unit='ms')
        spot_df.set_index('open_time', inplace=True)
        spot_df[['open', 'high', 'low', 'close', 'volume']] = spot_df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        save_data(spot_df, 'raw', f"{symbol.lower()}_spot_prices_{interval}")

        # 先物価格データの取得 (シンボルをBTCUSDTに変更)
        futures_symbol = 'BTCUSDT'
        futures_klines = client.futures_klines(symbol=futures_symbol, interval=interval, limit=limit)
        futures_df = pd.DataFrame(futures_klines, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ])
        futures_df['open_time'] = pd.to_datetime(futures_df['open_time'], unit='ms')
        futures_df['close_time'] = pd.to_datetime(futures_df['close_time'], unit='ms')
        futures_df.set_index('open_time', inplace=True)
        futures_df[['open', 'high', 'low', 'close', 'volume']] = futures_df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        save_data(futures_df, 'raw', f"{futures_symbol.lower()}_futures_prices_{interval}")

        return spot_df, futures_df

    except Exception as e:
        print(f"Error fetching or saving data: {e}")
        return None, None 
# src/config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# src/utils.py
import os
import pandas as pd
from config import OUTPUT_DIR

def save_data(data, subfolder, filename):
    folder_path = os.path.join(OUTPUT_DIR, subfolder)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{filename}.parquet")
    data.to_parquet(file_path, index=False)
    return file_path

def load_data(subfolder, filename):
    file_path = os.path.join(OUTPUT_DIR, subfolder, f"{filename}.parquet")
    if os.path.exists(file_path):
        return pd.read_parquet(file_path)
    return None

# src/binance_data.py
import os
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client
from config import BASE_DIR
from utils import save_data

def get_binance_client():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    return Client(api_key, api_secret)

def get_historical_data(months=3):
    client = get_binance_client()
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30 * months)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    spot_klines = client.get_historical_klines(
        symbol="BTCUSDT", 
        interval=Client.KLINE_INTERVAL_1DAY,
        start_str=start_str,
        end_str=end_str
    )
    
    futures_klines = client.futures_historical_klines(
        symbol="BTCUSDT",
        interval=Client.KLINE_INTERVAL_1DAY,
        start_str=start_str,
        end_str=end_str
    )
    
    spot_df = klines_to_dataframe(spot_klines)
    futures_df = klines_to_dataframe(futures_klines)
    
    save_data(spot_df, "raw", "btc_spot_prices")
    save_data(futures_df, "raw", "btc_futures_prices")
    
    return spot_df, futures_df

def klines_to_dataframe(klines):
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
        df[col] = df[col].astype(float)
    
    return df

# src/analysis.py
import pandas as pd
from utils import save_data, load_data

def calculate_basis(spot_df=None, futures_df=None):
    if spot_df is None:
        spot_df = load_data("raw", "btc_spot_prices")
    
    if futures_df is None:
        futures_df = load_data("raw", "btc_futures_prices")
    
    spot_df['date'] = spot_df['open_time'].dt.date
    futures_df['date'] = futures_df['open_time'].dt.date
    
    merged_df = pd.merge(
        spot_df[['date', 'close']].rename(columns={'close': 'spot_close'}),
        futures_df[['date', 'close']].rename(columns={'close': 'futures_close'}),
        on='date'
    )
    
    merged_df['basis'] = merged_df['futures_close'] - merged_df['spot_close']
    merged_df['basis_percent'] = (merged_df['basis'] / merged_df['spot_close']) * 100
    
    save_data(merged_df, "processed", "btc_basis")
    
    return merged_df

def analyze_basis(basis_df=None):
    if basis_df is None:
        basis_df = load_data("processed", "btc_basis")
    
    stats = basis_df.describe()
    
    basis_df['basis_ma7'] = basis_df['basis'].rolling(7).mean()
    basis_df['basis_percent_ma7'] = basis_df['basis_percent'].rolling(7).mean()
    
    save_data(stats, "analysis", "basis_statistics")
    save_data(basis_df, "analysis", "basis_with_ma")
    
    return stats, basis_df

# src/plot.py
import os
import pandas as pd
import matplotlib.pyplot as plt
from config import OUTPUT_DIR

def plot_and_save_data():
    plot_dir = os.path.join(OUTPUT_DIR, "plot")
    os.makedirs(plot_dir, exist_ok=True)
    
    # ベーシスデータのプロット
    basis_path = os.path.join(OUTPUT_DIR, "analysis", "basis_with_ma.parquet")
    if os.path.exists(basis_path):
        df = pd.read_parquet(basis_path)
        df_clean = df.dropna()
        
        # 日付をインデックスに設定
        if 'date' in df_clean.columns:
            df_clean = df_clean.set_index('date')
        
        # 各列ごとにサブプロット
        fig, axes = plt.subplots(nrows=len(df_clean.columns), figsize=(12, 3*len(df_clean.columns)))
        
        for i, col in enumerate(df_clean.columns):
            df_clean[col].plot(ax=axes[i], title=col)
        
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, "basis_analysis.png"))
        plt.close()
    
    # 価格データのプロット
    spot_path = os.path.join(OUTPUT_DIR, "raw", "btc_spot_prices.parquet")
    futures_path = os.path.join(OUTPUT_DIR, "raw", "btc_futures_prices.parquet")
    
    if os.path.exists(spot_path) and os.path.exists(futures_path):
        spot_df = pd.read_parquet(spot_path)
        futures_df = pd.read_parquet(futures_path)
        
        # 価格比較プロット
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(spot_df['open_time'], spot_df['close'], label='Spot Price')
        ax.plot(futures_df['open_time'], futures_df['close'], label='Futures Price')
        ax.set_title('BTC Spot vs Futures Price')
        ax.set_xlabel('Date')
        ax.set_ylabel('Price (USDT)')
        ax.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, "price_comparison.png"))
        plt.close()
        
        # ボリュームプロット
        fig, ax = plt.subplots(figsize=(12, 6))
        ax.bar(spot_df['open_time'], spot_df['volume'], alpha=0.5, label='Spot Volume')
        ax.set_title('BTC Spot Trading Volume')
        ax.set_xlabel('Date')
        ax.set_ylabel('Volume')
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, "volume.png"))
        plt.close()

# src/main.py
from binance_data import get_historical_data
from analysis import calculate_basis, analyze_basis
from plot import plot_and_save_data

def main():
    print("BTCの価格データを取得中...")
    spot_df, futures_df = get_historical_data(months=3)
    print(f"現物価格データ: {len(spot_df)}行")
    print(f"先物価格データ: {len(futures_df)}行")
    
    print("ベーシスを計算中...")
    basis_df = calculate_basis(spot_df, futures_df)
    print(f"ベーシスデータ: {len(basis_df)}行")
    
    print("分析を実行中...")
    stats, analyzed_df = analyze_basis(basis_df)
    
    print("グラフを生成中...")
    plot_and_save_data()
    
    print("処理が完了しました。")
    print(f"ベーシスの基本統計量:\n{stats['basis']}")

if __name__ == "__main__":
    main()

# requirements.txt
pandas==2.0.0
python-binance==1.0.17
pyarrow==14.0.1
matplotlib==3.7.1

---
Perplexity の Eliot より: pplx.ai/share
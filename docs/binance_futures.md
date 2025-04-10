# BTCの先物価格と現物価格の日時データ取得コード

Binance APIを使用してビットコインの先物価格と現物価格のデータを3か月分取得するPythonコードを作成しました。このコードでは、現物市場のBTC/USDTペアと無期限先物のBTC/USDTペアの日足データを取得します。

## 準備

まず、必要なライブラリをインポートし、APIキーを設定します。

```python
import os
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client

# 環境変数からAPIキーを取得
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# クライアントの初期化
client = Client(api_key, api_secret)
```

## データ取得期間の設定

3か月分のデータを取得するために、現在の日付から3か月前までの期間を設定します。

```python
# 3か月前の日付を計算
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

# 日付を文字列に変換
start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")
```

## 現物価格データの取得

Binance APIの`get_historical_klines`メソッドを使用して、BTCUSDTの現物価格データを取得します。

```python
# BTCの現物価格データを取得（日足）
print("現物価格データを取得中...")
spot_klines = client.get_historical_klines(
    symbol="BTCUSDT", 
    interval=Client.KLINE_INTERVAL_1DAY,
    start_str=start_str,
    end_str=end_str
)
```

## 先物価格データの取得

Binance APIの`futures_historical_klines`メソッドを使用して、BTCUSDTの無期限先物価格データを取得します。

```python
# BTCの無期限先物価格データを取得（USD決済先物、日足）
print("無期限先物価格データを取得中...")
futures_klines = client.futures_historical_klines(
    symbol="BTCUSDT",
    interval=Client.KLINE_INTERVAL_1DAY,
    start_str=start_str,
    end_str=end_str
)
```

## データの整形と保存

取得したデータをPandasのDataFrameに変換し、CSVファイルとして保存します。

```python
# データをDataFrameに変換する関数
def klines_to_dataframe(klines):
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    # ミリ秒タイムスタンプを日時に変換
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    # 数値データを浮動小数点に変換
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
        df[col] = df[col].astype(float)
    
    return df

# DataFrameに変換
spot_df = klines_to_dataframe(spot_klines)
futures_df = klines_to_dataframe(futures_klines)

# データを保存
spot_df.to_csv('btc_spot_prices_3months.csv', index=False)
futures_df.to_csv('btc_futures_prices_3months.csv', index=False)

print(f"現物価格データ: {len(spot_df)}行")
print(f"先物価格データ: {len(futures_df)}行")
print("データはCSVファイルに保存されました。")
```

## 先物と現物の価格差（ベーシス）計算

先物と現物の価格差（ベーシス）を計算し、分析用のデータを作成します。

```python
# 先物と現物の価格差（ベーシス）を計算
spot_df['date'] = spot_df['open_time'].dt.date
futures_df['date'] = futures_df['open_time'].dt.date

# 日付でマージして価格差を計算
merged_df = pd.merge(
    spot_df[['date', 'close']].rename(columns={'close': 'spot_close'}),
    futures_df[['date', 'close']].rename(columns={'close': 'futures_close'}),
    on='date'
)
merged_df['basis'] = merged_df['futures_close'] - merged_df['spot_close']
merged_df['basis_percent'] = (merged_df['basis'] / merged_df['spot_close']) * 100

# ベーシスデータを保存
merged_df.to_csv('btc_basis_3months.csv', index=False)
print("ベーシスデータもCSVファイルに保存されました。")
```

## 完全なコード

以下は、上記のすべての部分を組み合わせた完全なコードです。

```python
import os
import pandas as pd
from datetime import datetime, timedelta
from binance.client import Client

# 環境変数からAPIキーを取得
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_API_SECRET")

# クライアントの初期化
client = Client(api_key, api_secret)

# 3か月前の日付を計算
end_date = datetime.now()
start_date = end_date - timedelta(days=90)

# 日付を文字列に変換
start_str = start_date.strftime("%Y-%m-%d")
end_str = end_date.strftime("%Y-%m-%d")

# BTCの現物価格データを取得（日足）
print("現物価格データを取得中...")
spot_klines = client.get_historical_klines(
    symbol="BTCUSDT", 
    interval=Client.KLINE_INTERVAL_1DAY,
    start_str=start_str,
    end_str=end_str
)

# BTCの無期限先物価格データを取得（USD決済先物、日足）
print("無期限先物価格データを取得中...")
futures_klines = client.futures_historical_klines(
    symbol="BTCUSDT",
    interval=Client.KLINE_INTERVAL_1DAY,
    start_str=start_str,
    end_str=end_str
)

# データをDataFrameに変換する関数
def klines_to_dataframe(klines):
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    # ミリ秒タイムスタンプを日時に変換
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    # 数値データを浮動小数点に変換
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
        df[col] = df[col].astype(float)
    
    return df

# DataFrameに変換
spot_df = klines_to_dataframe(spot_klines)
futures_df = klines_to_dataframe(futures_klines)

# 先物と現物の価格差（ベーシス）を計算
spot_df['date'] = spot_df['open_time'].dt.date
futures_df['date'] = futures_df['open_time'].dt.date

# 日付でマージして価格差を計算
merged_df = pd.merge(
    spot_df[['date', 'close']].rename(columns={'close': 'spot_close'}),
    futures_df[['date', 'close']].rename(columns={'close': 'futures_close'}),
    on='date'
)
merged_df['basis'] = merged_df['futures_close'] - merged_df['spot_close']
merged_df['basis_percent'] = (merged_df['basis'] / merged_df['spot_close']) * 100

# データを保存
spot_df.to_csv('btc_spot_prices_3months.csv', index=False)
futures_df.to_csv('btc_futures_prices_3months.csv', index=False)
merged_df.to_csv('btc_basis_3months.csv', index=False)

print(f"現物価格データ: {len(spot_df)}行")
print(f"先物価格データ: {len(futures_df)}行")
print("すべてのデータがCSVファイルに保存されました。")
```

















# src/config.py
import os

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

# 必要なディレクトリを作成
os.makedirs(OUTPUT_DIR, exist_ok=True)

# src/utils.py
import os
import pandas as pd
from config import OUTPUT_DIR

def save_data(data, subfolder, filename):
    """データをparquetファイルとして保存する関数"""
    folder_path = os.path.join(OUTPUT_DIR, subfolder)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{filename}.parquet")
    data.to_parquet(file_path, index=False)
    return file_path

def load_data(subfolder, filename):
    """保存されたparquetファイルを読み込む関数"""
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
    """Binance APIクライアントを初期化する関数"""
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    return Client(api_key, api_secret)

def get_historical_data(months=3):
    """BTCの先物価格と現物価格の日時データを取得する関数"""
    client = get_binance_client()
    
    # 取得期間の設定
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30 * months)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # 現物価格データの取得
    spot_klines = client.get_historical_klines(
        symbol="BTCUSDT", 
        interval=Client.KLINE_INTERVAL_1DAY,
        start_str=start_str,
        end_str=end_str
    )
    
    # 先物価格データの取得
    futures_klines = client.futures_historical_klines(
        symbol="BTCUSDT",
        interval=Client.KLINE_INTERVAL_1DAY,
        start_str=start_str,
        end_str=end_str
    )
    
    # データをDataFrameに変換
    spot_df = klines_to_dataframe(spot_klines)
    futures_df = klines_to_dataframe(futures_klines)
    
    # データを保存
    save_data(spot_df, "raw", "btc_spot_prices")
    save_data(futures_df, "raw", "btc_futures_prices")
    
    return spot_df, futures_df

def klines_to_dataframe(klines):
    """Binance APIから取得したK線データをDataFrameに変換する関数"""
    df = pd.DataFrame(klines, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    # ミリ秒タイムスタンプを日時に変換
    df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
    df['close_time'] = pd.to_datetime(df['close_time'], unit='ms')
    
    # 数値データを浮動小数点に変換
    for col in ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume']:
        df[col] = df[col].astype(float)
    
    return df

# src/analysis.py
import pandas as pd
from utils import save_data, load_data

def calculate_basis(spot_df=None, futures_df=None):
    """先物と現物の価格差（ベーシス）を計算する関数"""
    if spot_df is None:
        spot_df = load_data("raw", "btc_spot_prices")
    
    if futures_df is None:
        futures_df = load_data("raw", "btc_futures_prices")
    
    # 日付列を追加
    spot_df['date'] = spot_df['open_time'].dt.date
    futures_df['date'] = futures_df['open_time'].dt.date
    
    # 日付でマージして価格差を計算
    merged_df = pd.merge(
        spot_df[['date', 'close']].rename(columns={'close': 'spot_close'}),
        futures_df[['date', 'close']].rename(columns={'close': 'futures_close'}),
        on='date'
    )
    
    # ベーシスと割合を計算
    merged_df['basis'] = merged_df['futures_close'] - merged_df['spot_close']
    merged_df['basis_percent'] = (merged_df['basis'] / merged_df['spot_close']) * 100
    
    # 結果を保存
    save_data(merged_df, "processed", "btc_basis")
    
    return merged_df

def analyze_basis(basis_df=None):
    """ベーシスデータの分析を行う関数"""
    if basis_df is None:
        basis_df = load_data("processed", "btc_basis")
    
    # 基本統計量を計算
    stats = basis_df.describe()
    
    # 移動平均を計算
    basis_df['basis_ma7'] = basis_df['basis'].rolling(7).mean()
    basis_df['basis_percent_ma7'] = basis_df['basis_percent'].rolling(7).mean()
    
    # 結果を保存
    save_data(stats, "analysis", "basis_statistics")
    save_data(basis_df, "analysis", "basis_with_ma")
    
    return stats, basis_df

# src/main.py
from binance_data import get_historical_data
from analysis import calculate_basis, analyze_basis

def main():
    """メイン処理を実行する関数"""
    # データの取得
    print("BTCの価格データを取得中...")
    spot_df, futures_df = get_historical_data(months=3)
    print(f"現物価格データ: {len(spot_df)}行")
    print(f"先物価格データ: {len(futures_df)}行")
    
    # ベーシスの計算
    print("ベーシスを計算中...")
    basis_df = calculate_basis(spot_df, futures_df)
    print(f"ベーシスデータ: {len(basis_df)}行")
    
    # 分析の実行
    print("分析を実行中...")
    stats, analyzed_df = analyze_basis(basis_df)
    
    print("処理が完了しました。")
    print(f"ベーシスの基本統計量:\n{stats['basis']}")

if __name__ == "__main__":
    main()

# requirements.txt
pandas==2.0.0
python-binance==1.0.17
pyarrow==14.0.1

---
Perplexity の Eliot より: pplx.ai/share
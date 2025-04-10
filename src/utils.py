import os
import pandas as pd
import pyarrow
from config import RAW_OUTPUT_DIR, PROCESSED_OUTPUT_DIR, ANALYSIS_OUTPUT_DIR

def save_data(df, data_type, filename):
    """データをファイルに保存する関数"""
    try:
        if data_type == "raw":
            filepath = os.path.join(RAW_OUTPUT_DIR, f"{filename}.parquet")
        elif data_type == "processed":
            filepath = os.path.join(PROCESSED_OUTPUT_DIR, f"{filename}.parquet")
        elif data_type == "analysis":
            filepath = os.path.join(ANALYSIS_OUTPUT_DIR, f"{filename}.parquet")
        else:
            print(f"Error: Unknown data_type: {data_type}")
            return
        df.to_parquet(filepath)
        print(f"Data successfully saved to {filepath}")
    except Exception as e:
        print(f"Error saving data: {e}")

def load_data(data_type, filename):
    """ファイルからデータを読み込む関数"""
    try:
        if data_type == "raw":
            filepath = os.path.join(RAW_OUTPUT_DIR, f"{filename}.parquet")
        elif data_type == "processed":
            filepath = os.path.join(PROCESSED_OUTPUT_DIR, f"{filename}.parquet")
        elif data_type == "analysis":
            filepath = os.path.join(ANALYSIS_OUTPUT_DIR, f"{filename}.parquet")
        else:
            print(f"Error: Unknown data_type: {data_type}")
            return None
        df = pd.read_parquet(filepath)
        return df
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return None
    except Exception as e:
        print(f"Error loading data: {e}")
        return None

def align_timestamps(spot_df, futures_df):
    """現物と先物のタイムスタンプを揃える関数"""
    merged_df = pd.merge(
        spot_df[['close']].rename(columns={'close': 'spot_close'}),
        futures_df[['close']].rename(columns={'close': 'futures_close'}),
        left_index=True,
        right_index=True,
        how='outer',  # 全データを保持
        suffixes=('_spot', '_futures')
    ).interpolate(method='time')  # 時間軸補間

    spot_aligned = merged_df[['spot_close']].rename(columns={'spot_close': 'close'}).dropna()
    futures_aligned = merged_df[['futures_close']].rename(columns={'futures_close': 'close'}).dropna()

    return spot_aligned, futures_aligned
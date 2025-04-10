# src/utils.py
import os
import pandas as pd
import pyarrow as pa # エラーハンドリングで使用
from config import OUTPUT_DIR

def save_data(data, subfolder, filename):
    """データをparquetファイルとして保存する関数（タイムスタンプを文字列変換）"""
    folder_path = os.path.join(OUTPUT_DIR, subfolder)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{filename}.parquet")

    data_to_save = data.copy() # 元のDataFrameを変更しないようにコピー

    try:
        # 文字列に変換したので、タイムスタンプ関連のオプションは不要
        data_to_save.to_parquet(file_path, index=True)
        print(f"Data successfully saved to {file_path}")
    except Exception as e:
        print(f"Error saving data to {file_path}: {e}")
        print("Data types causing issue (after potential conversion):")
        print(data_to_save.dtypes)
        # 問題の切り分け支援
        try:
            pa.Table.from_pandas(data_to_save, preserve_index=False)
            print("PyArrow table conversion check passed after string conversion.")
        except Exception as pa_e:
            print(f"Error converting DataFrame to PyArrow Table even after string conversion: {pa_e}")
            for col in data_to_save.columns:
                try:
                     pa.Table.from_pandas(data_to_save[[col]], preserve_index=False)
                except Exception as col_e:
                    print(f"  Column '{col}' ({data_to_save[col].dtype}) might be problematic: {col_e}")
        raise # エラーを再発生させる

    return file_path

def load_data(subfolder, filename):
    """保存されたparquetファイルを読み込む関数（タイムスタンプを再パース）"""
    file_path = os.path.join(OUTPUT_DIR, subfolder, f"{filename}.parquet")
    if os.path.exists(file_path):
        df = pd.read_parquet(file_path, index_col='open_time')
        # 保存時に文字列に変換した可能性のある列をタイムスタンプに再パース
        # (列名や内容に基づいて判断する必要があるが、ここでは単純化のためdatetime/open_time/close_timeを対象とする)
        #for col in ['datetime', 'open_time', 'close_time']:
        #    if col in df.columns and df[col].dtype == 'object':
        #        try:
        #            # errors='coerce' でパースできないものは NaT にする
        #            df[col] = pd.to_datetime(df[col], errors='coerce')
        #            print(f"Converted column '{col}' back to datetime.")
        #        except Exception as e:
        #            print(f"Warning: Failed to convert column '{col}' back to datetime: {e}")
        return df
    print(f"File not found: {file_path}")
    return None
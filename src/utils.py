# src/utils.py
import os
import pandas as pd
import pyarrow as pa # エラーハンドリングで使用
from config import OUTPUT_DIR

def save_data(data, subfolder, filename):
    """データをparquetファイルとして保存する関数（タイムスタンプをdatetime形式で保存）"""
    folder_path = os.path.join(OUTPUT_DIR, subfolder)
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{filename}.parquet")
    data_to_save = data.copy()  # 元のDataFrameを変更しないようにコピー

    # datetime型の列を特定
    datetime_columns = data_to_save.select_dtypes(include=['datetime64']).columns

    try:
        # datetime型の列をそのまま保存
        data_to_save.to_parquet(file_path, index=True)
        print(f"Data successfully saved to {file_path}")
        print(f"Datetime columns preserved: {list(datetime_columns)}")
    except Exception as e:
        print(f"Error saving data to {file_path}: {e}")
        print("Data types:")
        print(data_to_save.dtypes)
        raise  # エラーを再発生させる

    return file_path

def load_data(subfolder, filename):
    """保存されたparquetファイルを読み込む関数"""
    file_path = os.path.join(OUTPUT_DIR, subfolder, f"{filename}.parquet")
    if os.path.exists(file_path):
        df = pd.read_parquet(file_path)
        print(f"Data loaded from {file_path}")
        print("Data types:")
        print(df.dtypes)
        return df
    print(f"File not found: {file_path}")
    return None
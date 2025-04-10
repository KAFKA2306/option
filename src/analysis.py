import pandas as pd
from utils import save_data, load_data, align_timestamps
from config import ANALYSIS_OUTPUT_DIR
import os

def calculate_basis(spot_df, futures_df, interval):
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    if spot_df is None or futures_df is None:
        print("Input DataFrames cannot be None.")
        return None

    spot_aligned, futures_aligned = align_timestamps(spot_df, futures_df)

    merged_df = pd.merge(
        spot_aligned[['close']].rename(columns={'close': 'spot_close'}),
        futures_aligned[['close']].rename(columns={'close': 'futures_close'}),
        left_index=True,
        right_index=True,
        how='inner'
    )

    if merged_df.empty:
        print("Merged DataFrame is empty. Check timestamp alignment.")
        return None

    merged_df['basis'] = merged_df['futures_close'] - merged_df['spot_close']
    merged_df['basis_percent'] = (merged_df['basis'] / merged_df['spot_close']) * 100

    basis_filepath = os.path.join(ANALYSIS_OUTPUT_DIR, f"basis_data_{interval_str}.parquet")
    save_data(merged_df, "analysis", f"basis_data_{interval_str}")

    return merged_df

def analyze_basis(interval):
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    basis_df = load_data("analysis", f"basis_data_{interval_str}")

    if basis_df is None or basis_df.empty:
        print(f"Basis data not found or empty for interval: {interval_str}")
        return None, None

    stats = basis_df[['basis', 'basis_percent']].describe().round(5)

    if interval.endswith('h'):
        ma_period = 24
    elif interval.endswith('d'):
        ma_period = 7
    else:
        ma_period = 12

    basis_df = basis_df.sort_index()
    basis_df[f'basis_ma{ma_period}'] = basis_df['basis'].rolling(ma_period).mean()
    basis_df[f'basis_percent_ma{ma_period}'] = basis_df['basis_percent'].rolling(ma_period).mean()

    stats_filepath = os.path.join(ANALYSIS_OUTPUT_DIR, f"basis_statistics_{interval_str}.parquet")
    analysis_filepath = os.path.join(ANALYSIS_OUTPUT_DIR, f"basis_with_ma_{interval_str}.parquet")

    save_data(stats, "analysis", f"basis_statistics_{interval_str}")
    save_data(basis_df, "analysis", f"basis_with_ma_{interval_str}")

    return stats, basis_df
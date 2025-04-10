import pandas as pd
from utils import save_data, load_data
from binance.client import Client

def calculate_basis(spot_df=None, futures_df=None, interval=Client.KLINE_INTERVAL_1HOUR):
    """先物と現物の価格差（ベーシス）を計算する関数"""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')

    if spot_df is None:
        spot_df = load_data("raw", f"btc_spot_prices_{interval_str}")
    if futures_df is None:
        futures_df = load_data("raw", f"btc_futures_prices_{interval_str}")

    if spot_df is None or futures_df is None:
        print(f"必要なデータファイルが見つかりません: {interval_str}")
        return None

    # マージ前にタイムスタンプ列名を統一し、存在と型を確認
    for df, name in [(spot_df, "spot_df"), (futures_df, "futures_df")]:
        if 'open_time' not in df.columns:
            print(f"Error: '{name}' に 'open_time' 列が存在しません。")
            return None
        if not pd.api.types.is_datetime64_any_dtype(df['open_time']):
            print(f"Error: '{name}' の 'open_time' 列が datetime 型ではありません。")
            return None
        df['datetime'] = df.index

    merged_df = spot_df[['close']].rename(columns={'close': 'spot_close'})
    merged_df['futures_close'] = futures_df['close']
    # 日時でマージして価格差を計算 (indexを使用)
    merged_df = pd.merge(
        #spot_df[['datetime', 'close']].rename(columns={'close': 'spot_close'}),
        #futures_df[['datetime', 'close']].rename(columns={'close': 'futures_close'}),
        #on='datetime',
        #how='inner'  # 両方に存在する日時のみを対象とする
    )

    if merged_df.empty:
        print("マージ後のデータが空です。日時が一致しない可能性があります。")
        return None

    merged_df['basis'] = merged_df['futures_close'] - merged_df['spot_close']
    merged_df['basis_percent'] = (merged_df['basis'] / merged_df['spot_close']) * 100

    save_data(merged_df, "processed", f"btc_basis_{interval_str}")

    return merged_df

def analyze_basis(basis_df=None, interval=Client.KLINE_INTERVAL_1HOUR):
    """ベーシスデータの分析を行う関数"""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')

    if basis_df is None:
        basis_df = load_data("processed", f"btc_basis_{interval_str}")

    if basis_df is None or basis_df.empty:
        print(f"ベーシスデータファイルが見つかりません: {interval_str}")
        return None, None

    # describe()の結果を保存する前にインデックスをリセット
    stats = basis_df.describe()

    # 移動平均の期間を調整（1時間データの場合は24で1日）
    if interval == Client.KLINE_INTERVAL_1HOUR:
        ma_period = 24  # 24時間の移動平均
    elif interval == Client.KLINE_INTERVAL_1DAY:
        ma_period = 7   # 7日の移動平均
    else:
        ma_period = 12  # デフォルト

    # インデックスがdatetime型であることを確認し、必要に応じて設定・ソート
    #if not pd.api.types.is_datetime64_any_dtype(basis_df.index):
    #    print("Warning: DataFrameのインデックスがdatetime型ではありません。設定を試みます。")
    #    try:
    #        basis_df['datetime'] = pd.to_datetime(basis_df['datetime'])
    #        basis_df = basis_df.set_index('datetime').sort_index()
    #        print("インデックスをdatetime型に設定し、ソートしました。")
    #    except Exception as e:
    #        print(f"Error: datetime型への変換またはインデックス設定に失敗しました: {e}")
    #        return None, None

    if 'basis' in basis_df.columns and 'basis_percent' in basis_df.columns:
        basis_df[f'basis_ma{ma_period}'] = basis_df['basis'].rolling(ma_period).mean()
        basis_df[f'basis_percent_ma{ma_period}'] = basis_df['basis_percent'].rolling(ma_period).mean()
    else:
        print("Warning: 'basis' または 'basis_percent' 列が見つかりません。移動平均は計算されませんでした。")
        return None, None

    # 浮動小数点数の桁数を丸める
    stats = stats.round(5)
    stats = stats.reset_index()
    save_data(stats, "analysis", f"basis_statistics_{interval_str}", index=True)
    save_data(basis_df, "analysis", f"basis_with_ma_{interval_str}")

    return stats, basis_df
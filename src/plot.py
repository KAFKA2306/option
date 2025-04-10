import os
import pandas as pd
import matplotlib.pyplot as plt
from binance.client import Client
from config import OUTPUT_DIR
from utils import load_data

# 日本語フォント設定 (環境に合わせて調整)
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Hiragino Maru Gothic Pro', 'Yu Gothic', 'Meirio', 'TakaoPGothic']

def plot_and_save_data(interval=Client.KLINE_INTERVAL_1HOUR):
    """分析データを読み込み、グラフを生成して保存する関数"""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    filename = f"basis_with_ma_{interval_str}"
    print(f"Loading analysis data: {filename}")

    df = load_data("analysis", filename)

    if df is None or df.empty:
        print(f"Plotting skipped: Analysis data not found or empty for {filename}")
        return

    # プロットする列を選択 (例)
    plot_columns = [
        'spot_close',
        'futures_close',
        'basis',
        'basis_percent',
        f'basis_ma{24 if interval.endswith("h") else 7 if interval.endswith("d") else 12}',
        f'basis_percent_ma{24 if interval.endswith("h") else 7 if interval.endswith("d") else 12}'
    ]
    # 存在する列のみを対象にする
    plot_columns = [col for col in plot_columns if col in df.columns]

    if not plot_columns:
        print("Plotting skipped: No relevant columns found in the data.")
        return

    print(f"Plotting columns: {plot_columns}")
    n_cols = len(plot_columns)
    fig, axes = plt.subplots(nrows=n_cols, figsize=(15, 4 * n_cols), sharex=True)

    if n_cols == 1:
        axes = [axes] # 単一プロットの場合、axesをリストにする

    for i, col in enumerate(plot_columns):
        try:
            df[col].plot(ax=axes[i], title=col, grid=True)
            axes[i].set_ylabel(col)
        except Exception as e:
            print(f"Warning: Could not plot column '{col}'. Error: {e}")

    # x軸ラベルを最後のプロットにのみ表示
    axes[-1].set_xlabel("Datetime")

    fig.suptitle(f"Basis Analysis - Interval: {interval_str}", fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.98]) # suptitleとの重なりを調整

    # プロット保存用ディレクトリ作成
    plot_dir = os.path.join(OUTPUT_DIR, "plots")
    os.makedirs(plot_dir, exist_ok=True)

    save_path = os.path.join(plot_dir, f"basis_analysis_{interval_str}.png")
    try:
        plt.savefig(save_path)
        print(f"Plot saved to {save_path}")
    except Exception as e:
        print(f"Error saving plot: {e}")

    plt.close(fig) # メモリ解放のためフィギュアを閉じる

    # --- 価格データのプロット ---
    # Use the correct filenames as saved by data_loader.py, using the original interval
    spot_filename = f"btcusdt_spot_prices_{interval}"  # Use original interval
    futures_filename = f"btcusdt_futures_prices_{interval}" # Use original interval

    spot_df = load_data("raw", spot_filename)
    futures_df = load_data("raw", futures_filename)

    if spot_df is not None and not spot_df.empty and futures_df is not None and not futures_df.empty:
        # 価格比較プロット
        fig_price, ax_price = plt.subplots(figsize=(15, 7))
        try:
            # Assuming index is already datetime after loading parquet
            ax_price.plot(spot_df.index, spot_df['close'], label='Spot Price', linewidth=1)
            ax_price.plot(futures_df.index, futures_df['close'], label='Futures Price', linewidth=1, linestyle='--')
            ax_price.set_title(f'BTCUSDT 現物 vs 先物 価格 ({interval_str})') # Title updated
            ax_price.set_xlabel('日時')
            ax_price.set_ylabel('価格 (USDT)')
            ax_price.legend()
            ax_price.grid(True)
            plt.tight_layout()
            fig_price.savefig(os.path.join(plot_dir, f"price_comparison_{interval_str}.png"))
            print(f"価格比較グラフを保存しました: price_comparison_{interval_str}.png")
        except Exception as e:
            print(f"Error plotting price comparison: {e}")
        finally:
            plt.close(fig_price)

        # ボリュームプロット (現物)
        fig_vol, ax_vol = plt.subplots(figsize=(15, 7))
        try:
            bar_width = 0.03 if interval==Client.KLINE_INTERVAL_1HOUR else 0.8 # バー幅を動的に計算
            # Assuming index is already datetime
            ax_vol.bar(spot_df.index, spot_df['volume'], alpha=0.6, label='Spot Volume', width=bar_width)
            ax_vol.set_title(f'BTCUSDT 現物 取引量 ({interval_str})') # Title updated
            ax_vol.set_xlabel('日時')
            ax_vol.set_ylabel('取引量')
            ax_vol.grid(True, axis='y')
            plt.tight_layout()
            fig_vol.savefig(os.path.join(plot_dir, f"volume_{interval_str}.png"))
            print(f"出来高グラフを保存しました: volume_{interval_str}.png")
        except Exception as e:
            print(f"Error plotting volume: {e}")
        finally:
            plt.close(fig_vol)

        # 価格とボリュームの組み合わせプロット
        fig_pv, (ax_p, ax_v) = plt.subplots(2, 1, figsize=(15, 10), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
        try:
            # Assuming index is already datetime
            ax_p.plot(spot_df.index, spot_df['close'], label='Spot Price', linewidth=1)
            ax_p.set_title(f'BTCUSDT 価格と出来高 ({interval_str})') # Title updated
            ax_p.set_ylabel('価格 (USDT)')
            ax_p.legend()
            ax_p.grid(True)

            # Assuming index is already datetime
            ax_v.bar(spot_df.index, spot_df['volume'], alpha=0.6, label='Spot Volume', width=bar_width)
            ax_v.set_xlabel('日時')
            ax_v.set_ylabel('取引量')
            ax_v.legend()
            ax_v.grid(True, axis='y')

            plt.tight_layout()
            plt.subplots_adjust(hspace=0.1)
            fig_pv.savefig(os.path.join(plot_dir, f"price_volume_{interval_str}.png"))
            print(f"価格/出来高グラフを保存しました: price_volume_{interval_str}.png")
        except Exception as e:
            print(f"Error plotting price and volume: {e}")
        finally:
            plt.close(fig_pv)
    else:
        # Use interval_str for the warning message
        print(f"Warning: 価格データが見つからないか空です ({interval_str})")
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
    """分析結果のデータをプロットして保存する関数"""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')

    plot_dir = os.path.join(OUTPUT_DIR, "plot")
    os.makedirs(plot_dir, exist_ok=True)

    # --- ベーシスデータのプロット ---
    basis_df = load_data("analysis", f"basis_with_ma_{interval_str}")
    if basis_df is not None and not basis_df.empty:
        # インデックスがdatetime型であることを確認し、必要に応じて設定
        if not pd.api.types.is_datetime64_any_dtype(basis_df.index):
            print("Warning: ベーシスデータのインデックスがdatetime型ではありません。設定を試みます。")
            try:
                basis_df['datetime'] = pd.to_datetime(basis_df['datetime'], format='%Y-%m-%d %H:%M:%S')
                basis_df = basis_df.set_index('datetime').sort_index()
                print("インデックスをdatetime型に設定しました。")
            except Exception as e:
                print(f"Error: datetime型への変換またはインデックス設定に失敗しました: {e}")
                return  # プロットをスキップ

        plot_cols = basis_df.select_dtypes(include=['number']).columns
        if not plot_cols.empty:
            num_plots = len(plot_cols)
            fig, axes = plt.subplots(nrows=num_plots, figsize=(15, 3 * num_plots), sharex=True)

            if num_plots == 1:
                axes = [axes]  # 単一プロットの場合

            try:
                for i, col in enumerate(plot_cols):
                    axes[i].plot(basis_df.index, basis_df[col], title=f"{col} ({interval_str})")
                    axes[i].grid(True)

                plt.tight_layout()
                fig.savefig(os.path.join(plot_dir, f"basis_analysis_{interval_str}.png"))
                print(f"ベーシス分析グラフを保存しました: basis_analysis_{interval_str}.png")
            except Exception as e:
                print(f"Error plotting basis data: {e}")
            finally:
                plt.close(fig)
        else:
            print(f"Warning: プロット可能な数値列が見つかりません ({interval_str})")
    else:
        print(f"Warning: ベーシスデータが見つからないか空です ({interval_str})")

    # --- 価格データのプロット ---
    spot_df = load_data("raw", f"btc_spot_prices_{interval_str}")
    futures_df = load_data("raw", f"btc_futures_prices_{interval_str}")

    if spot_df is not None and not spot_df.empty and futures_df is not None and not futures_df.empty:
        # 価格比較プロット
        fig_price, ax_price = plt.subplots(figsize=(15, 7))
        try:
            ax_price.plot(pd.to_datetime(spot_df['open_time'], format='%Y-%m-%d %H:%M:%S'), spot_df['close'], label='Spot Price', linewidth=1)
            ax_price.plot(pd.to_datetime(futures_df['open_time'], format='%Y-%m-%d %H:%M:%S'), futures_df['close'], label='Futures Price', linewidth=1, linestyle='--')
            ax_price.set_title(f'BTC 現物 vs 先物 価格 ({interval_str})')
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
            ax_vol.bar(pd.to_datetime(spot_df['open_time'], format='%Y-%m-%d %H:%M:%S'), spot_df['volume'], alpha=0.6, label='Spot Volume', width=bar_width)
            ax_vol.set_title(f'BTC 現物 取引量 ({interval_str})')
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
            ax_p.plot(pd.to_datetime(spot_df['open_time'], format='%Y-%m-%d %H:%M:%S'), spot_df['close'], label='Spot Price', linewidth=1)
            ax_p.set_title(f'BTC 価格と出来高 ({interval_str})')
            ax_p.set_ylabel('価格 (USDT)')
            ax_p.legend()
            ax_p.grid(True)

            ax_v.bar(pd.to_datetime(spot_df['open_time'], format='%Y-%m-%d %H:%M:%S'), spot_df['volume'], alpha=0.6, label='Spot Volume', width=bar_width)
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
        print(f"Warning: 価格データが見つからないか空です ({interval_str})")
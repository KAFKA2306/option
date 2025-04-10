import os
from binance.client import Client
from src.data_loader import fetch_and_save_data
# Import the new advanced analysis function
from src.analysis import run_advanced_analysis
# Keep plot import, but comment out the call for now
# from src.plot import plot_and_save_data
from src.config import create_output_directories
import datetime
# Import the report generator function (ensure correct filename)
from src.reportgenerator import generate_html_report # Corrected import path
import webbrowser

def run_pipeline(interval):
    """指定された時間間隔でデータ取得から高度な分析までを実行するパイプライン"""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    print(f"\n===== Pipeline Start: Interval {interval_str} =====")

    # 1. データ取得と保存
    print(f"--- Step 1: Fetching and Saving Data ---")
    spot_df, futures_df = fetch_and_save_data(symbol='BTCUSDT', interval=interval)

    if spot_df is None or spot_df.empty or futures_df is None or futures_df.empty:
        print("Pipeline stopped: Failed to fetch or data is empty.")
        print(f"===== Pipeline End: Interval {interval_str} =====")
        return

    print(f"Spot data rows: {len(spot_df)}")
    print(f"Futures data rows: {len(futures_df)}")

    # 2. 高度なベーシス分析の実行
    print(f"\n--- Step 2: Running Advanced Analysis ---")
    # Replace old calls with the new function
    stats, analyzed_df = run_advanced_analysis(spot_df, futures_df, interval)

    if stats is None or analyzed_df is None or analyzed_df.empty:
        print("Pipeline stopped: Advanced analysis failed or resulted in empty data.")
        print(f"===== Pipeline End: Interval {interval_str} =====")
        return

    print(f"Advanced analysis complete. Analyzed data rows: {len(analyzed_df)}")
    if not stats.empty:
        print(f"Basic Statistics Summary:\n{stats.head()}") # Print head of stats

    # 3. プロット (一時的にコメントアウト)
    # print(f"\n--- Step 3: Plotting Data (Skipped) ---")
    # plot_and_save_data(interval=interval)

    print(f"===== Pipeline End: Interval {interval_str} =====")

def main():
    """メイン処理: 各時間間隔でパイプラインを実行し、レポートを生成"""
    create_output_directories()

    print("Starting main process...")
    # 1時間足データの処理
    run_pipeline(Client.KLINE_INTERVAL_1HOUR)

    # 日足データの処理
    run_pipeline(Client.KLINE_INTERVAL_1DAY)

    print("\n--- All pipeline processes completed ---")

    # 4. HTMLレポート生成 (現時点では古いデータ構造を期待している可能性あり)
    print("\n--- Step 4: Generating HTML Report ---")
    try:
        html_file_path = generate_html_report()
        if html_file_path:
            print(f"Attempting to open report: {html_file_path}")
            # Ensure the path is absolute for webbrowser
            abs_path = os.path.abspath(html_file_path)
            webbrowser.open('file://' + abs_path)
        else:
            print("HTML report generation failed, cannot open.")
    except Exception as e:
        print(f"Error generating or opening HTML report: {e}")

if __name__ == "__main__":
    main()

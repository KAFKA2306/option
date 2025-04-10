import os
from binance.client import Client
from data_loader import fetch_and_save_data, client # clientもインポート
from analysis import calculate_basis, analyze_basis
from plot import plot_and_save_data
from config import create_output_directories
import datetime
# Import the report generator function
from reportgenerator import generate_html_report

def run_pipeline(interval):
    """指定された時間間隔でデータ取得からプロットまでを実行する関数"""
    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    print(f"\n===== 処理開始: 間隔 {interval_str} =====")
    print(f"--- BTCの価格データを取得中... ---")

    spot_df, futures_df = fetch_and_save_data(symbol='BTCUSDT', interval=interval)

    if spot_df is None or spot_df.empty or futures_df is None or futures_df.empty:
        print("価格データの取得に失敗したか、データが空のため、後続処理をスキップします。")
        print(f"===== 処理終了: 間隔 {interval_str} =====")
        return

    print(f"現物価格データ: {len(spot_df)}行")
    print(f"先物価格データ: {len(futures_df)}行")

    print(f"\n--- ベーシスを計算中... ---")
    basis_df = calculate_basis(spot_df, futures_df, interval)

    if basis_df is None or basis_df.empty:
        print("ベーシス計算に失敗したか、データが空のため、後続処理をスキップします。")
        print(f"===== 処理終了: 間隔 {interval_str} =====")
        return

    print(f"ベーシスデータ: {len(basis_df)}行")

    print(f"\n--- 分析を実行中... ---")
    stats, analyzed_df = analyze_basis(interval)

    if stats is None and analyzed_df is None:
        print("分析に失敗したため、グラフ生成をスキップします。")
        print(f"===== 処理終了: 間隔 {interval_str} =====")
        return

    if stats is not None:
        print(f"ベーシスの基本統計量:\n{stats}") # statsがNoneでない場合のみ表示

    print(f"\n--- グラフを生成中... ---")
    plot_and_save_data(interval=interval)

    print(f"===== 処理終了: 間隔 {interval_str} =====")

def main():
    """メイン処理を実行する関数"""
    create_output_directories()
    # 1時間足データの処理
    run_pipeline(Client.KLINE_INTERVAL_1HOUR)

    # 日足データの処理
    run_pipeline(Client.KLINE_INTERVAL_1DAY)

    print("\n--- 全ての処理が完了しました ---")

    # Generate the HTML report after all pipelines are complete
    print("\n--- HTMLレポートを生成中... ---")
    try:
        html_file_path = generate_html_report()
        # Optionally open the report in a web browser
        import webbrowser
        webbrowser.open('file://' + os.path.abspath(html_file_path))
    except Exception as e:
        print(f"Error generating HTML report: {e}")

if __name__ == "__main__":
    main()

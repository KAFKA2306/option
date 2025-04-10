from binance.client import Client
from binance_data import get_historical_data
from analysis import calculate_basis, analyze_basis
from plot import plot_and_save_data
import os

def run_pipeline(interval):
    """指定された時間間隔でデータ取得からプロットまでを実行する関数"""
    import os
    from binance.client import Client

    # 環境変数からAPIキーを取得
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")

    # クライアントの初期化
    client = Client(api_key, api_secret)


    interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
    print(f"\n===== 処理開始: 間隔 {interval_str} =====")

    print(f"--- BTCの価格データを取得中... ---")
    try:
        spot_df, futures_df = get_historical_data(months=3, interval=interval)
    except ValueError as e: # APIキー未設定エラー
        print(f"エラー: {e}")
        return # 処理中断
    except Exception as e:
        print(f"データ取得中に予期せぬエラー: {e}")
        return # 処理中断

    if spot_df is None or spot_df.empty or futures_df is None or futures_df.empty:
        print("価格データの取得に失敗したか、データが空のため、後続処理をスキップします。")
        print(f"===== 処理終了: 間隔 {interval_str} =====")
        return

    print(f"現物価格データ: {len(spot_df)}行")
    print(f"先物価格データ: {len(futures_df)}行")

    print(f"\n--- ベーシスを計算中... ---")
    basis_df = calculate_basis(spot_df, futures_df, interval=interval)

    if basis_df is None or basis_df.empty:
        print("ベーシス計算に失敗したか、データが空のため、後続処理をスキップします。")
        print(f"===== 処理終了: 間隔 {interval_str} =====")
        return

    print(f"ベーシスデータ: {len(basis_df)}行")

    print(f"\n--- 分析を実行中... ---")
    stats, analyzed_df = analyze_basis(basis_df, interval=interval)

    if stats is None and analyzed_df is None:
         print("分析に失敗したため、グラフ生成をスキップします。")
         print(f"===== 処理終了: 間隔 {interval_str} =====")
         return

    if stats is not None:
         print(f"ベーシスの基本統計量:\n{stats['basis']}") # statsがNoneでない場合のみ表示

    print(f"\n--- グラフを生成中... ---")
    plot_and_save_data(interval=interval)

    print(f"===== 処理終了: 間隔 {interval_str} =====")


def main():
    """メイン処理を実行する関数"""
    # 1時間足データの処理
    run_pipeline(Client.KLINE_INTERVAL_1HOUR)

    # 日足データの処理
    run_pipeline(Client.KLINE_INTERVAL_1DAY)

    print("\n--- 全ての処理が完了しました ---")

if __name__ == "__main__":
    main()

# report_generator.py
import os
import pandas as pd
import datetime
import matplotlib.pyplot as plt
from jinja2 import Template
from binance.client import Client
import numpy as np # Import numpy for checking NaN

from config import OUTPUT_DIR, ANALYSIS_OUTPUT_DIR, BASE_DIR
from utils import load_data

def generate_html_report(intervals=[Client.KLINE_INTERVAL_1HOUR, Client.KLINE_INTERVAL_1DAY]):
    """
    指定された時間間隔でHTMLレポートを生成する関数 (高度な分析データを使用)
    
    Parameters:
    -----------
    intervals : list
        レポートを生成する時間間隔のリスト
    """
    # HTMLファイルの保存先をBASE_DIRに変更
    # report_dir = os.path.join(OUTPUT_DIR, "reports") # 旧パス
    # os.makedirs(report_dir, exist_ok=True) # 不要になる
    
    # 現在の日時
    now = datetime.datetime.now()
    report_date = now.strftime("%Y年%m月%d日 %H:%M:%S")
    
    # レポートに含めるデータを収集
    report_data = []
    
    for interval in intervals:
        interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
        print(f"Generating report section for interval: {interval_str}")
        
        # === データ読み込み (ファイル名を advanced_ に変更) ===
        stats_file = f"advanced_basis_stats_{interval_str}"
        stats_df = load_data("analysis", stats_file)
        if stats_df is None or stats_df.empty:
            print(f"Warning: Statistics data file '{stats_file}.parquet' not found or empty.")
            continue # Skip this interval if stats are missing

        analysis_file = f"advanced_basis_data_{interval_str}"
        analysis_df = load_data("analysis", analysis_file)
        if analysis_df is None or analysis_df.empty:
            print(f"Warning: Analysis data file '{analysis_file}.parquet' not found or empty.")
            continue # Skip this interval if analysis data is missing

        # === データ準備 ===
        start_date = analysis_df.index.min().strftime("%Y年%m月%d日")
        end_date = analysis_df.index.max().strftime("%Y年%m月%d日")
        
        # グラフのパス (相対パスに変更)
        basis_plot_path = os.path.join("output", "plots", f"basis_analysis_{interval_str}.png")
        price_plot_path = os.path.join("output", "plots", f"price_comparison_{interval_str}.png")
        volume_plot_path = os.path.join("output", "plots", f"volume_{interval_str}.png")
        price_volume_plot_path = os.path.join("output", "plots", f"price_volume_{interval_str}.png")
        
        # 直近の値を取得 (NaNをチェック)
        latest_data = analysis_df.iloc[-1].to_dict()
        # Format numbers, handle potential NaNs by converting to None or specific string
        formatted_latest = {}
        for key, value in latest_data.items():
            if pd.isna(value):
                formatted_latest[key] = 'N/A' # Or None, depending on template handling
            elif isinstance(value, (int, float)):
                 # Basic formatting, can be customized
                 if 'percent' in key or 'annualized' in key:
                     formatted_latest[key] = f"{value:.4f}"
                 elif key == 'basis_zscore':
                     formatted_latest[key] = f"{value:.2f}"
                 else:
                     formatted_latest[key] = f"{value:.2f}"
            else:
                 formatted_latest[key] = value # Keep non-numeric as is

        # 統計量の整形 (NaNを考慮)
        stats_html = stats_df.applymap(lambda x: '{:.5f}'.format(x) if pd.notna(x) else 'N/A').to_html(classes="table table-striped table-sm", border=0, escape=False)
        
        # 分析コメントの生成 (新しい指標を使用)
        analysis_comment = generate_analysis_comment_advanced(stats_df, analysis_df, interval)
        
        report_data.append({
            "interval": interval_str,
            "start_date": start_date,
            "end_date": end_date,
            "stats_html": stats_html,
            "latest_data": formatted_latest, # Use formatted data
            "basis_plot_path": basis_plot_path,
            "price_plot_path": price_plot_path,
            "volume_plot_path": volume_plot_path,
            "price_volume_plot_path": price_volume_plot_path,
            "analysis_comment": analysis_comment
        })
    
    if not report_data:
        print("No data available to generate the report.")
        return None # Return None if no data was processed

    # HTMLテンプレートの読み込み
    html_template = get_html_template_advanced()
    
    # HTMLレポートの生成
    html_content = html_template.render(
        report_date=report_date,
        report_data=report_data
    )
    
    # HTMLファイルの保存パスをBASE_DIR直下に変更
    html_file_path = os.path.join(BASE_DIR, "index.html")
    try:
        with open(html_file_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"HTML Report has been saved to {html_file_path}")
        return html_file_path
    except Exception as e:
        print(f"Error writing HTML report file: {e}")
        return None

def generate_analysis_comment_advanced(stats_df, analysis_df, interval):
    """
    高度な分析データを使用して分析コメントを生成する関数
    
    Parameters:
    -----------
    stats_df : DataFrame
        統計データ
    analysis_df : DataFrame
        分析データ
    interval : str
        時間間隔
    
    Returns:
    --------
    str
        生成された分析コメント
    """
    comment_parts = []
    interval_str = interval.replace('h', '時間').replace('d', '日') # More Japanese friendly

    comment_parts.append(f"<h4>ビットコイン先物ベーシス分析（{interval_str}）</h4>")
    comment_parts.append(f"<p>分析期間: {analysis_df.index.min().strftime('%Y年%m月%d日')} - {analysis_df.index.max().strftime('%Y年%m月%d日')}</p>")

    # Extract latest values safely, checking for column existence and NaN
    latest = analysis_df.iloc[-1]
    latest_basis = latest.get('basis', np.nan)
    latest_basis_percent = latest.get('basis_percent', np.nan)
    latest_annualized = latest.get('annualized_basis', np.nan)
    latest_zscore = latest.get('basis_zscore', np.nan)
    latest_regime = latest.get('market_regime', np.nan)

    # Extract stats safely
    mean_basis = stats_df.loc['mean', 'basis'] if 'basis' in stats_df.columns and 'mean' in stats_df.index else np.nan
    std_basis = stats_df.loc['std', 'basis'] if 'basis' in stats_df.columns and 'std' in stats_df.index else np.nan
    mean_basis_percent = stats_df.loc['mean', 'basis_percent'] if 'basis_percent' in stats_df.columns and 'mean' in stats_df.index else np.nan

    # --- 市場概況 ---
    comment_parts.append("<h5>市場概況</h5>")
    if not pd.isna(mean_basis):
        market_condition = "バックワーデーション（先物 < 現物）" if mean_basis < 0 else "コンタンゴ（先物 > 現物）"
        comment_parts.append(f"<p>期間中の市場は平均的に<strong>{market_condition}</strong>の状態でした。")
        comment_parts.append(f"平均ベーシス: {mean_basis:.2f}ドル ({mean_basis_percent:.4f}%)")
        if not pd.isna(latest_annualized):
             comment_parts.append(f"直近の年率換算ベーシス: {latest_annualized:.2f}%")
        comment_parts.append(f"標準偏差: {std_basis:.2f}ドル</p>")
    else:
        comment_parts.append("<p>市場概況の計算に必要なデータが不足しています。</p>")

    # --- 最新の状況 & レジーム ---
    comment_parts.append("<h5>最新の状況と市場レジーム</h5>")
    if not pd.isna(latest_basis):
        comment_parts.append(f"<p>最新ベーシス: {latest_basis:.2f}ドル ({latest_basis_percent:.4f}%)")

        regime_map = {0: "強いバックワーデーション", 1: "中立", 2: "強いコンタンゴ"}
        regime_text = regime_map.get(latest_regime, "不明") if pd.notna(latest_regime) else "不明"
        comment_parts.append(f"現在の市場レジーム: <strong>{regime_text}</strong>")

        if not pd.isna(latest_zscore):
            z_threshold = 2.0 # Standard threshold
            anomaly = abs(latest_zscore) > z_threshold
            comment_parts.append(f"ベーシスZスコア: {latest_zscore:.2f} " + \
                                 (f"(<strong>統計的に{ '高い' if latest_zscore > 0 else '低い' }水準です - 閾値: ±{z_threshold}</strong>)" if anomaly else "(平常範囲内)"))
        comment_parts.append("</p>")
    else:
         comment_parts.append("<p>最新状況の計算に必要なデータが不足しています。</p>")


    # --- 投資戦略への示唆 ---
    comment_parts.append("<h5>投資戦略への示唆</h5>")
    if not pd.isna(mean_basis):
        if mean_basis < 0: # バックワーデーション
             comment_parts.append("<p>平均的なバックワーデーションは、市場参加者の短期的な弱気心理や現物需要の強さを示唆します。")
             comment_parts.append("アービトラージ戦略としては「先物買い・現物売り」が考えられますが、")
             if not pd.isna(latest_zscore) and latest_zscore < -z_threshold:
                 comment_parts.append(f"<strong>現在のZスコア({latest_zscore:.2f})はこの戦略が有利である可能性を示唆しています。</strong>")
             else:
                 comment_parts.append("現在のZスコアは必ずしもこの戦略が有利とは限りません。")
             comment_parts.append("</p>")
        else: # コンタンゴ
             comment_parts.append("<p>平均的なコンタンゴは、将来価格への期待や保管コスト（キャリーコスト）を反映している可能性があります。")
             comment_parts.append("アービトラージ戦略としては「現物買い・先物売り」が考えられます。")
             if not pd.isna(latest_zscore) and latest_zscore > z_threshold:
                 comment_parts.append(f"<strong>現在のZスコア({latest_zscore:.2f})はこの戦略が有利である可能性を示唆しています。</strong>")
             else:
                 comment_parts.append("現在のZスコアは必ずしもこの戦略が有利とは限りません。")
             comment_parts.append("</p>")
    else:
         comment_parts.append("<p>投資戦略の示唆を生成するにはデータが不足しています。</p>")

    return "\\n".join(comment_parts)

def get_html_template_advanced():
    """
    HTMLテンプレートを取得する関数 (高度な分析対応版)
    
    Returns:
    --------
    Template
        Jinja2のテンプレートオブジェクト
    """
    html_template = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ビットコイン先物ベーシス高度分析レポート</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { font-family: 'Hiragino Sans', 'Yu Gothic', 'Meiryo', sans-serif; line-height: 1.6; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background-color: #f8f9fa; padding: 20px; margin-bottom: 30px; border-radius: 5px; border-left: 5px solid #007bff; }
            .section { margin-bottom: 40px; padding: 20px; background-color: #fff; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            .plot-container { text-align: center; margin-bottom: 30px;}
            .plot-image { max-width: 100%; height: auto; margin: 10px 0; border: 1px solid #ddd; border-radius: 5px; }
            h2 { color: #007bff; border-bottom: 2px solid #007bff; padding-bottom: 10px; margin-bottom: 20px; }
            h3 { color: #0056b3; margin-top: 30px; margin-bottom: 15px; }
            .latest-data-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px; background-color: #e9f7fe; padding: 15px; border-radius: 5px; margin-bottom: 20px;}
            .latest-data-item { font-size: 0.9em;}
            .footer { text-align: center; margin-top: 50px; padding: 20px; font-size: 0.9em; color: #6c757d; }
            .table-sm { font-size: 0.85rem; } /* Make table smaller */
            .comment-section { background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin-top: 20px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>ビットコイン先物ベーシス高度分析レポート</h1>
                <p>生成日時: {{ report_date }}</p>
            </div>
            
            <div class="section">
                <h2>要約</h2>
                <p>このレポートは、ビットコイン現物価格と先物価格の差（ベーシス）について、基本的な指標に加え、年率換算ベーシス、Zスコア、市場レジームなどの高度な分析を提供します。これにより、市場の状況をより深く理解し、投資戦略立案に役立てることを目的とします。</p>
                {% if report_data %}
                <p><strong>主な発見:</strong></p>
                <ul>
                    {% for data in report_data %}
                    <li><strong>{{ data.interval }}:</strong>
                        平均ベーシス: {{ data.stats_html.split('<td>mean</td>')[1].split('<td>')[1].split('</td>')[0] if '<td>mean</td>' in data.stats_html else 'N/A' }}ドル
                        ({{ data.stats_html.split('<td>mean</td>')[1].split('<td>')[2].split('</td>')[0] if '<td>mean</td>' in data.stats_html else 'N/A' }}%),
                        直近Zスコア: {{ data.latest_data.get('basis_zscore', 'N/A') }},
                        現レジーム: {{ {0: "バックワーデーション", 1: "中立", 2: "コンタンゴ"}.get(data.latest_data.get('market_regime'), '不明') if data.latest_data.get('market_regime') != 'N/A' else '不明' }}
                    </li>
                    {% endfor %}
                </ul>
                {% endif %}
            </div>
            
            {% for data in report_data %}
            <div class="section">
                <h2>{{ data.interval }} 分析</h2>
                <p><strong>期間:</strong> {{ data.start_date }} から {{ data.end_date }} まで</p>
                
                <h3>最新の主要指標</h3>
                <div class="latest-data-grid">
                    <div class="latest-data-item"><strong>現物価格:</strong> {{ data.latest_data.get('spot_price', 'N/A') }} $</div>
                    <div class="latest-data-item"><strong>先物価格:</strong> {{ data.latest_data.get('futures_price', 'N/A') }} $</div>
                    <div class="latest-data-item"><strong>ベーシス:</strong> {{ data.latest_data.get('basis', 'N/A') }} $</div>
                    <div class="latest-data-item"><strong>ベーシス率:</strong> {{ data.latest_data.get('basis_percent', 'N/A') }} %</div>
                    <div class="latest-data-item"><strong>年率換算ベーシス:</strong> {{ data.latest_data.get('annualized_basis', 'N/A') }} %</div>
                    <div class="latest-data-item"><strong>ベーシスZスコア:</strong> {{ data.latest_data.get('basis_zscore', 'N/A') }}</div>
                    <div class="latest-data-item"><strong>市場レジーム:</strong> {{ {0: "バックワーデーション", 1: "中立", 2: "コンタンゴ"}.get(data.latest_data.get('market_regime'), '不明') if data.latest_data.get('market_regime') != 'N/A' else '不明' }}</div>
                    <div class="latest-data-item"><strong>ボラティリティ調整済ベーシス:</strong> {{ data.latest_data.get('vol_adjusted_basis', 'N/A') }}</div>
                </div>
                
                <h3>統計分析サマリー</h3>
                <div class="table-responsive">
                    {{ data.stats_html|safe }}
                </div>
                
                <h3>グラフ分析</h3>
                <div class="plot-container">
                    <img src="{{ data.basis_plot_path }}" alt="ベーシス分析グラフ" class="plot-image">
                </div>
                 <div class="row">
                     <div class="col-md-6 plot-container">
                         <img src="{{ data.price_plot_path }}" alt="価格比較グラフ" class="plot-image">
                     </div>
                     <div class="col-md-6 plot-container">
                         <img src="{{ data.volume_plot_path }}" alt="取引量グラフ" class="plot-image">
                     </div>
                 </div>
                 <div class="plot-container">
                      <img src="{{ data.price_volume_plot_path }}" alt="価格と取引量グラフ" class="plot-image">
                 </div>

                <h3>分析コメント</h3>
                <div class="comment-section">
                    {{ data.analysis_comment|safe }}
                </div>
            </div>
            {% endfor %}
            
            <div class="footer">
                <p>© {{ report_date[:4] }} ビットコイン先物ベーシス高度分析レポート</p>
            </div>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    
    return Template(html_template)

def calculate_market_insights(analysis_df):
    """
    市場洞察を計算する関数
    
    Parameters:
    -----------
    analysis_df : DataFrame
        分析データ
        
    Returns:
    --------
    dict
        市場洞察を含む辞書
    """
    # 過去30日間のデータ
    recent_df = analysis_df.iloc[-30:]
    
    # ベーシスの傾向
    basis_trend = recent_df['basis'].iloc[-1] > recent_df['basis'].iloc[0]
    trend_str = "上昇" if basis_trend else "下降"
    
    # ボラティリティ
    recent_volatility = recent_df['basis'].std()
    overall_volatility = analysis_df['basis'].std()
    vol_change = (recent_volatility / overall_volatility - 1) * 100
    vol_str = "増加" if vol_change > 0 else "減少"
    
    return {
        "basis_trend": trend_str,
        "vol_change": vol_change,
        "vol_str": vol_str,
        "recent_vol": recent_volatility,
        "overall_vol": overall_volatility
    }

if __name__ == "__main__":
    # レポートの生成
    html_file_path = generate_html_report()
    
    if html_file_path:
        # Webブラウザでレポートを開く
        import webbrowser
        webbrowser.open('file://' + os.path.abspath(html_file_path))

# report_generator.py
import os
import pandas as pd
import datetime
from jinja2 import Template
from binance.client import Client
import numpy as np

from config import OUTPUT_DIR, ANALYSIS_OUTPUT_DIR, BASE_DIR
from utils import load_data

# --- Helper Function for Formatting Stats ---
def format_stats_df(df):
    """Formats the statistics DataFrame for better HTML display."""
    formatted_df = df.copy()
    if formatted_df.empty:
        return formatted_df

    # Identify numeric columns (excluding potential non-numeric ones if any)
    numeric_cols = formatted_df.select_dtypes(include=np.number).columns

    for col in numeric_cols:
        if 'percent' in col or 'annualized' in col:
            # Format percentages with 4 decimal places and '%' sign
            formatted_df[col] = formatted_df[col].apply(lambda x: f'{x:.4f}%' if pd.notna(x) else 'N/A')
        elif 'zscore' in col:
             # Format Z-score with 2 decimal places
            formatted_df[col] = formatted_df[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else 'N/A')
        elif col in ['basis', 'spot_price', 'futures_price']:
            # Format prices/basis with 2 decimal places
            formatted_df[col] = formatted_df[col].apply(lambda x: f'{x:,.2f}' if pd.notna(x) else 'N/A') # Add comma separators
        else:
            # Default numeric formatting (e.g., for counts, std, min, max if not price/percent/zscore)
            formatted_df[col] = formatted_df[col].apply(lambda x: f'{x:.2f}' if pd.notna(x) else 'N/A')

    # Make index more readable (e.g., replace '25%' with '25th Percentile')
    formatted_df.index = formatted_df.index.astype(str).str.replace('25%', '25th Pct').str.replace('50%', 'Median (50th Pct)').str.replace('75%', '75th Pct')
    formatted_df.index.name = "指標" # Set index name

    return formatted_df

def generate_html_report(intervals=[Client.KLINE_INTERVAL_1HOUR, Client.KLINE_INTERVAL_1DAY]):
    """
    指定された時間間隔でHTMLレポートを生成する関数 (高度な分析データを使用)
    
    Parameters:
    -----------
    intervals : list
        レポートを生成する時間間隔のリスト
    """
    html_file_path = os.path.join(BASE_DIR, "index.html")
    now = datetime.datetime.now()
    report_date = now.strftime("%Y年%m月%d日 %H:%M:%S JST") # Add timezone indication

    report_data = []

    for interval in intervals:
        interval_str = interval.replace('m', 'min').replace('h', 'hour').replace('d', 'day').replace('w', 'week')
        print(f"Generating report section for interval: {interval_str}")

        stats_file = f"advanced_basis_stats_{interval_str}"
        stats_df_raw = load_data("analysis", stats_file) # Load raw stats
        if stats_df_raw is None or stats_df_raw.empty:
            print(f"Warning: Statistics data file '{stats_file}.parquet' not found or empty.")
            continue

        analysis_file = f"advanced_basis_data_{interval_str}"
        analysis_df = load_data("analysis", analysis_file)
        if analysis_df is None or analysis_df.empty:
            print(f"Warning: Analysis data file '{analysis_file}.parquet' not found or empty.")
            continue

        # --- データ準備 ---
        analysis_df.index = pd.to_datetime(analysis_df.index) # Ensure index is datetime
        start_dt = analysis_df.index.min()
        end_dt = analysis_df.index.max()
        duration_days = (end_dt - start_dt).days + 1
        start_date_str = start_dt.strftime("%Y年%m月%d日")
        end_date_str = end_dt.strftime("%Y年%m月%d日")
        period_str = f"{start_date_str} から {end_date_str} まで ({duration_days}日間)" # Improved period string

        # --- グラフパス ---
        advanced_basis_plot_path = os.path.join("output", "plots", f"advanced_basis_analysis_{interval_str}.png")
        strategy_perf_plot_path = os.path.join("output", "plots", f"strategy_performance_{interval_str}.png")

        # --- 最新データ整形 ---
        latest_data = analysis_df.iloc[-1].to_dict()
        formatted_latest = {}
        for key, value in latest_data.items():
            if pd.isna(value):
                formatted_latest[key] = 'N/A'
            elif isinstance(value, (int, float)):
                if 'percent' in key or 'annualized' in key:
                    formatted_latest[key] = f"{value:.4f}%"
                elif key == 'basis_zscore':
                    formatted_latest[key] = f"{value:.2f}"
                elif key in ['basis', 'spot_price', 'futures_price']:
                     formatted_latest[key] = f"{value:,.2f}" # Add comma
                else:
                    formatted_latest[key] = f"{value:.2f}"
            else: # Handle market regime etc.
                 formatted_latest[key] = value

        # --- 統計量 整形 & HTML化 ---
        stats_display_df = format_stats_df(stats_df_raw) # Use helper function
        stats_html = stats_display_df.to_html(classes="table table-bordered table-striped table-sm table-hover", border=0, escape=False) # Added table-bordered and table-hover

        # --- 分析コメント生成 ---
        analysis_comment = generate_analysis_comment_advanced(stats_df_raw, analysis_df, interval) # Pass raw stats

        report_data.append({
            "interval": interval_str,
            "period_str": period_str, # Use improved period string
            "stats_html": stats_html,
            "latest_data": formatted_latest,
            "advanced_basis_plot_path": advanced_basis_plot_path,
            "strategy_perf_plot_path": strategy_perf_plot_path,
            "analysis_comment": analysis_comment
        })

    if not report_data:
        print("No data available to generate the report.")
        return None

    # --- HTML生成 & 保存 ---
    html_template = get_html_template_advanced()
    html_content = html_template.render(
        report_date=report_date,
        report_data=report_data
    )
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
    高度な分析データを使用して、より具体的な分析コメントを生成する関数
    
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
    interval_jp = interval.replace('h', '時間').replace('d', '日')
    z_threshold = 2.0 # Define threshold

    comment_parts.append(f"<h4>ビットコイン先物ベーシス分析（{interval_jp}）</h4>")
    start_date = analysis_df.index.min().strftime('%Y年%m月%d日')
    end_date = analysis_df.index.max().strftime('%Y年%m月%d日')
    duration_days = (analysis_df.index.max() - analysis_df.index.min()).days + 1
    comment_parts.append(f"<p><strong>分析期間:</strong> {start_date} - {end_date} ({duration_days}日間)</p>")

    # --- Extract values safely ---
    latest = analysis_df.iloc[-1]
    latest_basis = latest.get('basis', np.nan)
    latest_basis_percent = latest.get('basis_percent', np.nan)
    latest_annualized = latest.get('annualized_basis', np.nan)
    latest_zscore = latest.get('basis_zscore', np.nan)
    latest_regime = latest.get('market_regime', np.nan)
    mean_basis = stats_df.loc['mean', 'basis'] if 'basis' in stats_df.columns and 'mean' in stats_df.index else np.nan
    std_basis = stats_df.loc['std', 'basis'] if 'basis' in stats_df.columns and 'std' in stats_df.index else np.nan
    mean_basis_percent = stats_df.loc['mean', 'basis_percent'] if 'basis_percent' in stats_df.columns and 'mean' in stats_df.index else np.nan
    mean_zscore = stats_df.loc['mean', 'basis_zscore'] if 'basis_zscore' in stats_df.columns and 'mean' in stats_df.index else np.nan
    std_zscore = stats_df.loc['std', 'basis_zscore'] if 'basis_zscore' in stats_df.columns and 'std' in stats_df.index else np.nan

    # --- 市場概況 ---
    comment_parts.append("<h5>市場概況</h5>")
    if not pd.isna(mean_basis):
        market_condition = "バックワーデーション" if mean_basis < 0 else "コンタンゴ"
        condition_detail = "（先物 < 現物）" if mean_basis < 0 else "（先物 > 現物）"
        avg_annualized = stats_df.loc['mean', 'annualized_basis'] if 'annualized_basis' in stats_df.columns and 'mean' in stats_df.index else np.nan

        comment_parts.append(f"<p>期間中の市場は平均的に<strong>{market_condition}{condition_detail}</strong>の状態でした。")
        comment_parts.append(f"<ul><li>平均ベーシス: {mean_basis:,.2f}ドル ({mean_basis_percent:.4f}%)</li>") # Added comma
        if pd.notna(avg_annualized):
             comment_parts.append(f"<li>平均年率換算ベーシス: {avg_annualized:.2f}%</li>")
        comment_parts.append(f"<li>ベーシスの標準偏差: {std_basis:,.2f}ドル</li></ul></p>") # Added comma
    else:
        comment_parts.append("<p>市場概況の計算に必要なデータが不足しています。</p>")

    # --- 最新の状況 & レジーム & Zスコア ---
    comment_parts.append("<h5>最新の状況、市場レジーム、Zスコア</h5>")
    if not pd.isna(latest_basis):
        regime_map = {0: "強いバックワーデーション", 1: "中立", 2: "強いコンタンゴ"}
        regime_text = regime_map.get(latest_regime, "不明") if pd.notna(latest_regime) else "不明"
        comment_parts.append(f"<p>最新の状況は以下の通りです:")
        comment_parts.append(f"<ul><li>最新ベーシス: {latest_basis:,.2f}ドル ({latest_basis_percent:.4f}%)</li>") # Added comma
        if pd.notna(latest_annualized):
            comment_parts.append(f"<li>最新年率換算ベーシス: {latest_annualized:.2f}%</li>")
        comment_parts.append(f"<li>市場レジーム: <strong>{regime_text}</strong></li>")
        if pd.notna(latest_zscore):
            anomaly = abs(latest_zscore) > z_threshold
            z_position = f"(平均比 {(latest_zscore - mean_zscore) / std_zscore:.1f}σ)" if pd.notna(mean_zscore) and pd.notna(std_zscore) and std_zscore != 0 else ""
            comment_parts.append(f"<li>ベーシスZスコア: {latest_zscore:.2f} {z_position} " + \
                                 (f"<span class='text-danger'><strong>(統計的に{ '高い' if latest_zscore > 0 else '低い' }水準 - 閾値: ±{z_threshold})</strong></span>" if anomaly else "(平常範囲内)") + "</li>")
        comment_parts.append("</ul></p>")
    else:
         comment_parts.append("<p>最新状況の計算に必要なデータが不足しています。</p>")

    # --- 投資戦略への示唆 ---
    comment_parts.append("<h5>投資戦略への示唆</h5>")
    if not pd.isna(mean_basis) and not pd.isna(latest_zscore):
        strat_suffix = "（先物買い・現物売り）" if market_condition == "バックワーデーション" else "（現物買い・先物売り）"
        is_favorable = (market_condition == "バックワーデーション" and latest_zscore < -z_threshold) or \
                       (market_condition == "コンタンゴ" and latest_zscore > z_threshold)

        comment_parts.append(f"<p>現在の市場状況 ({market_condition}) とZスコア ({latest_zscore:.2f}) を考慮すると、")
        comment_parts.append(f"統計的にはアービトラージ戦略{strat_suffix}が " + \
                             (f"<strong class='text-success'>特に有利である可能性</strong> が示唆されます。" if is_favorable else "現時点では必ずしも有利とは言えません。") + \
                             " Zスコアが閾値 (±{:.1f}) を超えているかどうかが判断材料の一つとなります。</p>".format(z_threshold))
    else:
         comment_parts.append("<p>投資戦略の示唆を生成するにはデータが不足しています。</p>")

    return "\n".join(comment_parts)

def get_html_template_advanced():
    """
    HTMLテンプレートを取得する関数 (改善提案適用版)
    
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
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { font-family: 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', sans-serif; line-height: 1.6; padding: 20px; background-color: #f0f2f5; }
            .container { max-width: 1200px; margin: 1rem auto; background-color: #fff; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
            .header { background-color: #e3f2fd; padding: 1.5rem; margin-bottom: 2rem; border-radius: 5px; border-left: 5px solid #0d6efd; }
            .header h1 { color: #0a58ca; }
            .section { margin-bottom: 2.5rem; padding-top: 1rem; }
            .plot-container { text-align: center; margin-bottom: 1.5rem; padding: 1rem; background-color: #f8f9fa; border-radius: 5px; }
            .plot-image { max-width: 100%; height: auto; margin: 0.5rem 0; border: 1px solid #dee2e6; border-radius: 5px; }
            h2 { color: #0d6efd; border-bottom: 2px solid #0d6efd; padding-bottom: 0.6rem; margin-bottom: 1.5rem; margin-top: 1rem; }
            h3 { color: #0a58ca; margin-top: 2rem; margin-bottom: 1rem; font-weight: 600; }
            h4.graph-title { background-color: #f5f5f5; padding: 8px 12px; border-left: 4px solid #0d6efd; margin-top: 1.5rem; margin-bottom: 1rem; display: inline-block; border-radius: 3px; font-weight: bold; font-size: 1.1rem; }
            .latest-data-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; background-color: #e9f7fe; padding: 1rem; border-radius: 5px; margin-bottom: 1.5rem; border: 1px solid #bde0fe;}
            .latest-data-item { font-size: 0.9em; padding: 0.5rem; background-color: #fff; border-radius: 3px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); }
            .latest-data-item strong { color: #0a58ca; }
            .footer { text-align: center; margin-top: 3rem; padding: 1.5rem; font-size: 0.9em; color: #6c757d; border-top: 1px solid #dee2e6; }
            .table-sm { font-size: 0.85rem; }
            .table-responsive { margin-top: 1rem; }
            .comment-section { background-color: #f8f9fa; padding: 1.5rem; border-radius: 5px; margin-top: 1.5rem; border: 1px solid #eee;}
            .comment-section h5 { margin-top: 0.5rem; color: #495057; font-weight: bold; }
            .comment-section ul { padding-left: 1.2rem; }
            .text-danger { color: #dc3545 !important; }
            .text-success { color: #198754 !important; }
            #toc { margin-bottom: 2rem; padding: 1rem; background-color: #f8f9fa; border-radius: 5px; }
            #toc ul { padding-left: 0; list-style: none; }
            #toc li a { text-decoration: none; color: #0d6efd; }
            #toc li a:hover { text-decoration: underline; }

            /* Responsive table */
            @media (max-width: 768px) {
                .table-responsive {
                    overflow-x: auto; /* Enable horizontal scroll */
                    -webkit-overflow-scrolling: touch; /* Smooth scrolling on iOS */
                }
                /* Ensure table itself doesn't shrink columns too much */
                .table-responsive > .table {
                   /* white-space: nowrap; /* Prevent text wrapping if needed */
                   /* Optional: min-width ensures table content dictates width */
                   min-width: 600px; /* Adjust as needed */
                }
                .latest-data-grid { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); } /* Adjust grid for smaller screens */
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>ビットコイン先物ベーシス高度分析レポート</h1>
                <p><strong>最終更新日時:</strong> {{ report_date }}</p>
            </div>

            <nav id="toc">
                <h5>目次</h5>
                <ul>
                    <li><a href="#summary">要約</a></li>
                    {% for data in report_data %}
                    <li><a href="#analysis-{{ data.interval }}">{{ data.interval }} 分析</a></li>
                    {% endfor %}
                    <li><a href="#glossary">用語集</a></li>
                </ul>
            </nav>

            <div class="section" id="summary">
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
                        現レジーム: {{ {0: "強いバックワーデーション", 1: "中立", 2: "強いコンタンゴ"}.get(data.latest_data.get('market_regime'), '不明') if data.latest_data.get('market_regime') != 'N/A' else '不明' }}
                    </li>
                    {% endfor %}
                </ul>
                {% else %}
                <p>分析データがありません。</p>
                {% endif %}
            </div>

            {% for data in report_data %}
            <div class="section" id="analysis-{{ data.interval }}">
                <h2>{{ data.interval }} 分析</h2>
                <p><strong>分析期間:</strong> {{ data.period_str }}</p>

                <h3>最新の主要指標</h3>
                <div class="latest-data-grid">
                    <div class="latest-data-item"><strong>現物価格:</strong> {{ data.latest_data.get('spot_price', 'N/A') }} $</div>
                    <div class="latest-data-item"><strong>先物価格:</strong> {{ data.latest_data.get('futures_price', 'N/A') }} $</div>
                    <div class="latest-data-item"><strong>ベーシス:</strong> {{ data.latest_data.get('basis', 'N/A') }} $</div>
                    <div class="latest-data-item"><strong>ベーシス率:</strong> {{ data.latest_data.get('basis_percent', 'N/A') }}</div>
                    <div class="latest-data-item"><strong>年率換算ベーシス:</strong> {{ data.latest_data.get('annualized_basis', 'N/A') }}</div>
                    <div class="latest-data-item"><strong>ベーシスZスコア:</strong> {{ data.latest_data.get('basis_zscore', 'N/A') }}</div>
                    <div class="latest-data-item"><strong>市場レジーム:</strong> {{ {0: "強いバックワーデーション", 1: "中立", 2: "強いコンタンゴ"}.get(data.latest_data.get('market_regime'), '不明') if data.latest_data.get('market_regime') != 'N/A' else '不明' }}</div>
                    <div class="latest-data-item"><strong>ボラティリティ調整済ベーシス:</strong> {{ data.latest_data.get('vol_adjusted_basis', 'N/A') }}</div>
                </div>

                <h3>統計分析サマリー</h3>
                <div class="table-responsive">
                    {{ data.stats_html|safe }}
                </div>

                <h3>グラフ分析</h3>
                <h4 class="graph-title">高度ベーシス分析</h4>
                <div class="plot-container">
                    <img src="{{ data.advanced_basis_plot_path }}" alt="高度ベーシス分析グラフ" class="plot-image">
                </div>
                <h4 class="graph-title">戦略パフォーマンス</h4>
                <div class="plot-container">
                    <img src="{{ data.strategy_perf_plot_path }}" alt="戦略パフォーマンスグラフ" class="plot-image">
                </div>

                <h3>分析コメント</h3>
                <div class="comment-section">
                    {{ data.analysis_comment|safe }}
                </div>
            </div>
            {% endfor %}

            <div class="section" id="glossary">
                <h2>用語集</h2>
                <dl class="row">
                    <dt class="col-sm-3">ベーシス</dt>
                    <dd class="col-sm-9">先物価格と現物価格の価格差（先物価格 - 現物価格）。市場の需給、期待、キャリーコストなどを反映します。</dd>
                    <dt class="col-sm-3">コンタンゴ</dt>
                    <dd class="col-sm-9">先物価格が現物価格より高い状態（ベーシス > 0）。通常の状態とされ、保管コストや将来価格への期待を示唆します。</dd>
                    <dt class="col-sm-3">バックワーデーション</dt>
                    <dd class="col-sm-9">先物価格が現物価格より低い状態（ベーシス < 0）。現物の強い需要や短期的な弱気心理を示唆することがあります。</dd>
                    <dt class="col-sm-3">年率換算ベーシス</dt>
                    <dd class="col-sm-9">ベーシスを満期までの期間を考慮して年率に換算したもの。異なる限月のベーシスを比較する際に有用です。</dd>
                    <dt class="col-sm-3">ベーシスZスコア</dt>
                    <dd class="col-sm-9">ベーシス（通常はベーシス率）が、過去の一定期間の平均から標準偏差の何倍離れているかを示す指標。統計的な割高・割安の判断に使われます。</dd>
                    <dt class="col-sm-3">市場レジーム</dt>
                    <dd class="col-sm-9">市場が特定の状態（例: 強いコンタンゴ、中立、強いバックワーデーション）にあることを示す分類。</dd>
                </dl>
            </div>

            <div class="footer">
                <p>© {{ report_date[:4] }} ビットコイン先物ベーシス高度分析レポート</p>
            </div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
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
    html_file_path = generate_html_report()
    if html_file_path:
        import webbrowser
        webbrowser.open('file://' + os.path.abspath(html_file_path))

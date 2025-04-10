# report_generator.py
import os
import pandas as pd
import datetime
import matplotlib.pyplot as plt
from jinja2 import Template
from binance.client import Client

from config import OUTPUT_DIR, ANALYSIS_OUTPUT_DIR, BASE_DIR
from utils import load_data

def generate_html_report(intervals=[Client.KLINE_INTERVAL_1HOUR, Client.KLINE_INTERVAL_1DAY]):
    """
    指定された時間間隔でHTMLレポートを生成する関数
    
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
        
        # 統計データの読み込み
        stats_file = f"basis_statistics_{interval_str}"
        stats_df = load_data("analysis", stats_file)
        if stats_df is None:
            print(f"Warning: Statistics data file '{stats_file}.parquet' not found.")
            continue
            
        # 分析データの読み込み
        analysis_file = f"basis_with_ma_{interval_str}"
        analysis_df = load_data("analysis", analysis_file)
        if analysis_df is None:
            print(f"Warning: Analysis data file '{analysis_file}.parquet' not found.")
            continue
        
        # 期間の情報
        start_date = analysis_df.index.min().strftime("%Y年%m月%d日")
        end_date = analysis_df.index.max().strftime("%Y年%m月%d日")
        
        # グラフのパス (相対パスに変更)
        basis_plot_path = os.path.join("output", "plots", f"basis_analysis_{interval_str}.png")
        price_plot_path = os.path.join("output", "plots", f"price_comparison_{interval_str}.png")
        volume_plot_path = os.path.join("output", "plots", f"volume_{interval_str}.png")
        price_volume_plot_path = os.path.join("output", "plots", f"price_volume_{interval_str}.png")
        
        # 直近の値を取得
        latest_data = analysis_df.iloc[-1].to_dict()
        
        # 統計量の整形
        stats_html = stats_df.to_html(classes="table table-striped table-sm", border=0, float_format='{:.5f}'.format)
        
        # 分析コメントの生成
        analysis_comment = generate_analysis_comment(stats_df, analysis_df, interval)
        
        report_data.append({
            "interval": interval_str,
            "start_date": start_date,
            "end_date": end_date,
            "stats_html": stats_html,
            "latest_data": latest_data,
            "basis_plot_path": basis_plot_path,
            "price_plot_path": price_plot_path,
            "volume_plot_path": volume_plot_path,
            "price_volume_plot_path": price_volume_plot_path,
            "analysis_comment": analysis_comment
        })
    
    # HTMLテンプレートの読み込み
    html_template = get_html_template()
    
    # HTMLレポートの生成
    html_content = html_template.render(
        report_date=report_date,
        report_data=report_data
    )
    
    # HTMLファイルの保存パスをBASE_DIR直下に変更
    html_file_path = os.path.join(BASE_DIR, "index.html")
    with open(html_file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"HTML Report has been saved to {html_file_path}")
    return html_file_path

def generate_analysis_comment(stats_df, analysis_df, interval):
    """
    分析コメントを生成する関数
    
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
    # 基本統計量から情報を抽出
    mean_basis = stats_df.loc['mean', 'basis']
    mean_basis_percent = stats_df.loc['mean', 'basis_percent']
    std_basis = stats_df.loc['std', 'basis']
    min_basis = stats_df.loc['min', 'basis']
    max_basis = stats_df.loc['max', 'basis']
    
    # 最新の値を取得
    latest_basis = analysis_df['basis'].iloc[-1]
    latest_basis_percent = analysis_df['basis_percent'].iloc[-1]
    
    # MAのカラム名を決定
    if interval.endswith('h'):
        ma_period = 24
    elif interval.endswith('d'):
        ma_period = 7
    else:
        ma_period = 12
    
    ma_col = f'basis_ma{ma_period}'
    if ma_col in analysis_df.columns:
        latest_ma = analysis_df[ma_col].iloc[-1]
        ma_trend = "上昇" if latest_basis > latest_ma else "下降"
    else:
        ma_trend = "不明"
    
    # 市場状態の判定
    market_condition = "バックワーデーション（先物価格が現物価格より低い）" if mean_basis < 0 else "コンタンゴ（先物価格が現物価格より高い）"
    
    # 異常値の検出
    z_score = (latest_basis - mean_basis) / std_basis if std_basis != 0 else 0
    anomaly = abs(z_score) > 2  # 2シグマを超える場合は異常とみなす
    
    # コメントの生成
    comment = f"""
    <h4>ビットコインのベーシス分析（{interval}）</h4>
    <p>
        分析期間: {analysis_df.index.min().strftime('%Y年%m月%d日')} - {analysis_df.index.max().strftime('%Y年%m月%d日')}
    </p>
    
    <h5>市場概況</h5>
    <p>
        現在の市場は<strong>{market_condition}</strong>の状態にあります。
        平均ベーシスは{mean_basis:.2f}ドル（{mean_basis_percent:.4f}%）で、
        標準偏差は{std_basis:.2f}ドルです。
        期間中の最小値は{min_basis:.2f}ドル、最大値は{max_basis:.2f}ドルでした。
    </p>
    
    <h5>最新の状況</h5>
    <p>
        最新のベーシスは{latest_basis:.2f}ドル（{latest_basis_percent:.4f}%）で、
        移動平均に対して{ma_trend}トレンドにあります。
        {"<strong>これは統計的に異常な値です。</strong>" if anomaly else ""}
    </p>
    
    <h5>投資戦略への示唆</h5>
    <p>
        現在の{market_condition}状態は、
        {"リスク回避姿勢が強い状態を示しています。機関投資家は慎重な姿勢を示していると考えられます。" if mean_basis < 0 else "楽観的な将来予測や買い需要の高まりを示しています。"}
        ベーシスの{f'負の値（{mean_basis:.2f}）' if mean_basis < 0 else f'正の値（{mean_basis:.2f}）'}は、
        {"短期的には先物を買い、現物を売る形のアービトラージ機会が存在する可能性があります。" if mean_basis < 0 else "短期的には現物を買い、先物を売る形のアービトラージ機会が存在する可能性があります。"}
    </p>
    
    <h5>注目ポイント</h5>
    <p>
        今後注目すべきポイントは以下の通りです：
        <ul>
            <li>ベーシスがゼロに接近するかどうか（市場心理の変化のシグナル）</li>
            <li>ボラティリティの変化（ベーシスの標準偏差が拡大するか）</li>
            <li>マクロ経済イベント（FRBの金利決定など）の影響</li>
        </ul>
    </p>
    """
    
    return comment

def get_html_template():
    """
    HTMLテンプレートを取得する関数
    
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
        <title>ビットコイン先物ベーシス分析レポート</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                font-family: 'Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', sans-serif;
                line-height: 1.6;
                color: #333;
                padding: 20px;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            .header {
                background-color: #f8f9fa;
                padding: 20px;
                margin-bottom: 30px;
                border-radius: 5px;
                border-left: 5px solid #007bff;
            }
            .section {
                margin-bottom: 40px;
                padding: 20px;
                background-color: #fff;
                border-radius: 5px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .stats-table {
                margin: 20px 0;
            }
            .plot-image {
                width: 100%;
                max-width: 1000px;
                margin: 20px 0;
                border: 1px solid #ddd;
                border-radius: 5px;
            }
            h2 {
                color: #007bff;
                border-bottom: 2px solid #007bff;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            h3 {
                color: #0056b3;
                margin-top: 30px;
                margin-bottom: 15px;
            }
            .latest-data {
                background-color: #e9f7fe;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }
            .footer {
                text-align: center;
                margin-top: 50px;
                padding: 20px;
                font-size: 0.9em;
                color: #6c757d;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>ビットコイン先物ベーシス分析レポート</h1>
                <p>生成日時: {{ report_date }}</p>
            </div>
            
            <div class="section">
                <h2>要約</h2>
                <p>
                    このレポートでは、ビットコイン先物と現物の価格差（ベーシス）を分析し、
                    市場のシグナルや投資戦略への示唆を提供します。
                    ベーシスは市場の需給バランス、投資家心理、将来の価格期待を反映する重要な指標です。
                </p>
                
                <p>
                    <strong>主な発見:</strong>
                    <ul>
                        {% for data in report_data %}
                        <li>
                            {{ data.interval }}間隔での平均ベーシス: 
                            {{ data.stats_html.split('<td>')[9].split('</td>')[0] }}ドル
                            ({{ data.stats_html.split('<td>')[10].split('</td>')[0] }}%)
                        </li>
                        {% endfor %}
                    </ul>
                </p>
            </div>
            
            {% for data in report_data %}
            <div class="section">
                <h2>{{ data.interval }} 分析</h2>
                
                <h3>期間</h3>
                <p>{{ data.start_date }} から {{ data.end_date }} まで</p>
                
                <h3>最新の状態</h3>
                <div class="latest-data">
                    <p><strong>最新のベーシス:</strong> {{ "%.2f"|format(data.latest_data.basis) }} ドル ({{ "%.4f"|format(data.latest_data.basis_percent) }}%)</p>
                    {% if 'basis_ma24' in data.latest_data %}
                    <p><strong>24時間移動平均ベーシス:</strong> {{ "%.2f"|format(data.latest_data.basis_ma24) }} ドル</p>
                    {% elif 'basis_ma7' in data.latest_data %}
                    <p><strong>7日移動平均ベーシス:</strong> {{ "%.2f"|format(data.latest_data.basis_ma7) }} ドル</p>
                    {% endif %}
                </div>
                
                <h3>統計分析</h3>
                <div class="stats-table">
                    {{ data.stats_html|safe }}
                </div>
                
                <h3>グラフ分析</h3>
                <h4>ベーシス分析</h4>
                <img src="{{ data.basis_plot_path }}" alt="ベーシス分析" class="plot-image">
                
                <h4>価格比較</h4>
                <img src="{{ data.price_plot_path }}" alt="価格比較" class="plot-image">
                
                <h4>取引量</h4>
                <img src="{{ data.volume_plot_path }}" alt="取引量" class="plot-image">
                
                <h4>価格と取引量</h4>
                <img src="{{ data.price_volume_plot_path }}" alt="価格と取引量" class="plot-image">
                
                <h3>分析コメント</h3>
                <div class="analysis-comment">
                    {{ data.analysis_comment|safe }}
                </div>
            </div>
            {% endfor %}
            
            <div class="section">
                <h2>結論と投資戦略への応用</h2>
                <p>
                    ビットコイン先物ベーシスの分析は、市場の現状理解と将来予測において貴重な洞察を提供します。
                    {% if report_data and report_data[0].stats_html.split('<td>')[9].split('</td>')[0]|float < 0 %}
                    現在のバックワーデーション状態（ベーシスがマイナス）は市場の慎重な姿勢を示していますが、
                    歴史的データによれば、このような状況は買いの機会となる可能性もあります。
                    {% else %}
                    現在のコンタンゴ状態（ベーシスがプラス）は市場の楽観的な姿勢を示していますが、
                    過度なプレミアムは将来の調整リスクを示唆している可能性もあります。
                    {% endif %}
                </p>
                
                <p>
                    投資家は、ベーシスのトレンド、サポート/レジスタンスレベル、ボラティリティの変化を注視し、
                    適切なリスク管理の下で投資戦略を構築することが重要です。
                    また、季節性要因も考慮に入れ、中長期的な視点での投資判断が求められます。
                </p>
                
                <p>
                    最終的に、ビットコイン先物ベーシスは単なる価格差以上の意味を持ち、
                    市場心理や将来の価格動向を読み解くための重要な指標となります。
                    これを適切に分析・活用することで、より洗練された投資判断が可能になるでしょう。
                </p>
            </div>
            
            <div class="footer">
                <p>© {{ report_date[:4] }} ビットコイン先物ベーシス分析レポート</p>
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
    
    # Webブラウザでレポートを開く（オプション）
    import webbrowser
    webbrowser.open('file://' + os.path.abspath(html_file_path))

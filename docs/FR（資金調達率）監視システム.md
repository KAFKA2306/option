# FR（資金調達率）監視システム：アーキテクチャ設計・実装ガイド

## 1. 概要

### 1.1 目的

本ドキュメントは、暗号通貨取引所におけるFR（資金調達率）をリアルタイムで収集・処理・監視するシステムのアーキテクチャ設計と実装に関する技術的な指針を提供します。これにより、市場の異常検知、リスク管理の強化、および潜在的な取引機会の特定を支援します。

### 1.2 システム概要

本システムは、主要な暗号通貨取引所からAPI経由でFRデータを取得し、Apache Kafkaを中心としたデータパイプラインを通じて処理・分析します。処理されたデータはElasticsearchに格納され、Grafanaダッシュボードで可視化・監視されます。異常値はリアルタイムで検知され、アラート通知が行われます。

### 1.3 対象読者

*   システムアーキテクト
*   ソフトウェア開発者（バックエンド、データエンジニアリング）
*   インフラストラクチャエンジニア
*   システム運用担当者

## 2. アーキテクチャ設計

### 2.1 高レベルアーキテクチャ

```mermaid
graph TD
    subgraph "データソース (取引所 API)"
        A[Binance API]
        B[Bybit API]
        C[OKX API]
        D[...]
    end

    subgraph "データ収集層 (FR Collector)"
        E[Python Collector Service (Docker)]
    end

    subgraph "メッセージキュー (Apache Kafka)"
        F[Kafka Cluster (v2.3.0.6 - **要移行計画**)]
        G[Topic: funding-rates-raw]
        H[Topic: funding-rates-processed]
        I[Topic: fr-anomalies]
    end

    subgraph "ストリーム処理層 (FR Processor)"
        J[Kafka Streams App / Flink Job (Docker)]
    end

    subgraph "データ永続化層"
        K[Kafka Connect]
        L[Elasticsearch Cluster]
    end

    subgraph "監視・可視化層"
        M[Grafana]
        N[Alertmanager (Optional)]
    end

    A -- REST API --> E
    B -- REST API --> E
    C -- REST API --> E
    D -- REST API --> E
    E -- Produce --> G

    G -- Consume --> J
    J -- Produce --> H
    J -- Produce --> I

    H -- Consume (via Kafka Connect) --> K
    K -- Index --> L

    L -- Data Source --> M
    I -- Consume --> N(アラート通知)
    M -- Query --> L
    N -- Notify --> O(Slack/Emailなど)

    style F fill:#f9f,stroke:#333,stroke-width:2px
```

### 2.2 コンポーネント詳細

1.  **データソース (取引所 API)**: Binance, Bybit, OKXなどの主要取引所が提供するFR取得用REST APIエンドポイント。
2.  **データ収集層 (FR Collector)**:
    *   技術スタック: Python 3.x, `requests`, `python-kafka`
    *   役割: 各取引所APIから定期的にFRデータを取得し、前処理（タイムスタンプ統一など）を行い、Kafkaの`funding-rates-raw`トピックへ送信する。
    *   デプロイ: Dockerコンテナ
3.  **メッセージキュー (Apache Kafka)**:
    *   バージョン: 2.3.0.6 (**注記：EOLバージョンであり、早期のアップグレード（3.x以降）を強く推奨**)
    *   役割: データ収集層、処理層、永続化層間の非同期メッセージング基盤。耐障害性とスケーラビリティを提供。
    *   主要トピック:
        *   `funding-rates-raw`: 収集された生データ
        *   `funding-rates-processed`: 正規化・加工されたデータ
        *   `fr-anomalies`: 異常検知されたデータ
4.  **ストリーム処理層 (FR Processor)**:
    *   技術スタック: Kafka Streams (Java/Scala) または Apache Flink (Java/Scala/Python)
    *   役割: `funding-rates-raw`トピックからデータを消費し、正規化、データエンリッチメント（例：現物価格との比較による乖離率計算）、異常検知（Z-scoreなど）を実行。結果を`funding-rates-processed`および`fr-anomalies`トピックへ送信。
    *   デプロイ: Dockerコンテナ
5.  **データ永続化層**:
    *   技術スタック: Kafka Connect (Elasticsearch Sink Connector), Elasticsearch Cluster
    *   役割: `funding-rates-processed`トピックのデータをElasticsearchに永続化する。
    *   Elasticsearch: 時系列データの検索、集計、分析に利用。
6.  **監視・可視化層**:
    *   技術スタック: Grafana, Alertmanager (オプション)
    *   役割: Elasticsearchのデータをデータソースとして、FRのトレンド、取引所間の比較、異常値などをダッシュボードで可視化。`fr-anomalies`トピックやGrafanaのアラートルールに基づき、Alertmanager等を通じて通知を行う。

### 2.3 データフロー

1.  FR Collectorが各取引所APIをポーリングし、FRデータを取得。
2.  取得した生データ（JSON形式）をKafkaの`funding-rates-raw`トピックに送信。
3.  FR Processorが`funding-rates-raw`からデータを消費。
4.  FR Processor内で、データのクリーニング、フォーマット統一、必要に応じて追加情報（乖離率など）の付与、異常検知処理を実行。
5.  処理済みデータは`funding-rates-processed`トピックへ、異常検知されたデータは`fr-anomalies`トピックへ送信。
6.  Kafka Connect (Elasticsearch Sink) が`funding-rates-processed`からデータを消費し、Elasticsearchへインデキシング。
7.  GrafanaがElasticsearchからデータを取得し、ダッシュボードに表示。
8.  Alertmanager（またはGrafana Alerting）が`fr-anomalies`トピックを監視（またはGrafanaのルールに基づき）、閾値超過時にアラートを発行。

### 2.4 技術選定の根拠

*   **Python (Collector)**: 豊富なHTTPライブラリとエコシステム、迅速な開発。
*   **Kafka**: 高スループット、耐障害性、スケーラビリティに優れたメッセージング基盤。ストリーム処理の基盤としても機能。
*   **Kafka Streams/Flink (Processor)**: ステートフルなストリーム処理、ウィンドウ処理、低レイテンシ処理に適している。
*   **Elasticsearch**: 高速な全文検索と時系列データ分析能力、集計機能。
*   **Grafana**: 豊富なデータソース対応、柔軟なダッシュボード構築、アラート機能。
*   **Docker**: コンポーネントの分離、デプロイの容易化、環境再現性。

### 2.5 非機能要件

*   **スケーラビリティ**: Kafkaのパーティション追加、Collector/Processorインスタンスの水平スケールアウトにより対応。
*   **可用性**: Kafkaクラスタのレプリケーション、コンポーネントの冗長化（複数インスタンス実行）、Elasticsearchクラスタ構成により担保。
*   **耐障害性**: Kafkaのメッセージ永続化と再送メカニズム、ステートフル処理のチェックポイント/ステートストアにより担保。
*   **監視性**: 各コンポーネントのメトリクス（JMX, Prometheus Exporterなど）を収集し、Grafanaで監視。

## 3. API統合

### 3.1 対象APIリスト（例）

| 取引所    | エンドポイント                          | 更新頻度 | レート制限/注意点          |
| :-------- | :-------------------------------------- | :------- | :------------------------- |
| Binance   | `/fapi/v1/fundingRate` (Perpetual)    | 1時間?   | 1200 req/min (IP weight)   |
|           | `/fapi/v1/premiumIndex` (価格指標)    | リアルタイム |                            |
| Bybit     | `/v5/market/funding/history`          | 8時間    | 10 req/sec (Endpoint別)   |
|           | `/v5/market/tickers?category=linear` | リアルタイム |                            |
| OKX       | `/api/v5/public/funding-rate`         | 8時間    | 20 req/2sec (Endpoint別)  |
|           | `/api/v5/market/ticker`               | リアルタイム |                            |
| ※Coinglass | (Webスクレイピング or 有料API)         | -        | 利用規約確認、不安定性あり |

### 3.2 データ取得ロジック (Python Collector)

```python
import requests
import time
import logging
from kafka import KafkaProducer
import json
import os
from datetime import datetime, timezone

# --- 設定 ---
KAFKA_BROKER = os.environ.get('KAFKA_BROKER', 'kafka:9092')
FETCH_INTERVAL_SECONDS = 300 # 5分ごとに主要APIをチェック (FR更新自体はもっと遅い)
RATE_LIMIT_DELAY = 0.5 # APIコール間の基本的な遅延

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

producer = KafkaProducer(
    bootstrap_servers=[KAFKA_BROKER],
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    acks='all', # 高信頼性設定
    retries=5,  # 再試行設定
    retry_backoff_ms=1000 # 再試行間隔
)

def fetch_binance_fr():
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"limit": 100} # 必要に応じてシンボルを指定
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status() # ステータスコードが200番台以外なら例外発生
        data = response.json()
        logging.info(f"Fetched {len(data)} FR records from Binance.")
        return data
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching Binance FR: {e}")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding Binance response: {e}")
        return None

# --- 他の取引所用の関数を追加 (fetch_bybit_fr, fetch_okx_fr 등) ---
# BybitやOKXは更新頻度が低いので、取得間隔を調整する必要があるかもしれない

def normalize_and_send(raw_data, source_exchange):
    if not raw_data:
        return 0

    count = 0
    for item in raw_data:
        try:
            # --- データ正規化 ---
            # 各取引所のレスポンス形式に合わせて必須フィールドを抽出・変換
            # 例: Binanceの場合
            normalized_record = {
                "exchange": source_exchange,
                "symbol": item.get('symbol'),
                "fundingRate": float(item.get('fundingRate', 0.0)),
                "fundingTime": int(item.get('fundingTime', 0)), # Unixミリ秒
                "markPrice": float(item.get('markPrice', 0.0)), # 参考価格（存在すれば）
                "fetchTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000) # 取得タイムスタンプ
            }

            # fundingTimeが未来か確認 (過去データでないことを保証)
            if normalized_record["fundingTime"]  processedStream = rawStream
    .mapValues((key, rawRate) -> { /* ... データ正規化 ... */ return processedRate; })
    .groupByKey() // シンボルでグループ化
    .windowedBy(TimeWindows.of(Duration.ofHours(24)).advanceBy(Duration.ofMinutes(5))) // 24時間ウィンドウ、5分ごと計算
    .aggregate(
        () -> new StatsAccumulator(), // 初期値 (count, sum, sumSquares)
        (key, value, aggregate) -> aggregate.add(value.getFundingRate()), // 集約ロジック
        Materialized.>as("fr-stats-store")
            .withKeySerde(Serdes.String())
            .withValueSerde(JsonSerdes.StatsAccumulator()) // カスタムSerde
    )
    .toStream()
    .mapValues((windowedKey, stats) -> {
        // 最新のレートを取得する必要がある（この例では省略）
        double currentRate = ... ; // 最新のレートを別途取得 or aggregate結果に含める
        double mean = stats.getMean();
        double stdDev = stats.getStdDev();
        double zScore = (stdDev > 0) ? (currentRate - mean) / stdDev : 0.0;
        boolean isAnomaly = Math.abs(zScore) > 3.0; // 閾値 (例: 3σ)

        // 元のprocessedRateに isAnomaly, zScore を設定して返す
        ProcessedFundingRate resultRate = ... ;
        resultRate.setIsAnomaly(isAnomaly);
        // resultRate.setZScore(zScore); // スキーマにあれば

        if (isAnomaly) {
            // fr-anomalies トピックにも送信
            AnomalyRecord anomaly = new AnomalyRecord(..., zScore, 3.0, resultRate);
            // anomaliesProducer.send("fr-anomalies", key, anomaly);
        }
        return resultRate;
    });

processedStream.to("funding-rates-processed", Produced.with(Serdes.String(), JsonSerdes.ProcessedFundingRate()));
```

*   **状態管理**: Kafka Streams/Flinkは内部的にRocksDBなどのステートストアを使用してウィンドウ計算の状態を保持する。
*   **ウィンドウ**: 要件に応じて適切なウィンドウタイプ（タンブリング、ホッピング、セッション）を選択。
*   **閾値**: 異常と判断するZ-score（または他の指標）の閾値は、過去データ分析やビジネス要件に基づいて決定。動的に調整する仕組みも検討可能。

## 7. データ永続化 (Elasticsearch)

### 7.1 Kafka Connect 設定 (Elasticsearch Sink)

```json
// es-sink-connector.json
{
  "name": "elasticsearch-sink-fr-processed",
  "config": {
    "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "3", // パーティション数に合わせて調整
    "topics": "funding-rates-processed",
    "connection.url": "http://elasticsearch:9200", // Elasticsearchエンドポイント
    "type.name": "_doc", // ES 7.x 以降の推奨
    "index": "funding_rates_processed_current", // 書き込み用エイリアス
    "key.ignore": "true", // Kafkaメッセージキーは無視
    "schema.ignore": "true", // スキーマ情報は無視 (スキーマレジストリ未使用の場合)
    "value.converter": "org.apache.kafka.connect.json.JsonConverter", // または AvroConverter
    "value.converter.schemas.enable": "false", // スキーマレジストリ未使用の場合 true
    //"value.converter.schema.registry.url": "http://schema-registry:8081", // Avroの場合
    "behavior.on.malformed.documents": "WARN", // 不正なドキュメントの処理方法
    "behavior.on.null.values": "IGNORE", // null値の処理
    "flush.timeout.ms": "10000",
    "batch.size": "2000",
    "max.retries": "10",
    "retry.backoff.ms": "5000"
    // ILM (Index Lifecycle Management) 連携設定 (オプション)
    //"index.lifecycle.policy.name": "fr_ilm_policy",
    //"index.rollover.alias": "funding_rates_processed_current"
  }
}
```

*   **デプロイ**: Kafka Connect Workerを起動し、上記設定ファイルをREST API経由でPOSTする。
*   **注意**: 使用するConnectorのバージョンによって設定項目が異なる場合があるため、公式ドキュメントを参照。

### 7.2 インデックスローテーション (ILM)

*   ElasticsearchのILM機能を使用して、インデックスサイズや経過時間に基づいて自動的に新しいインデックスを作成（Rollover）し、古いインデックスを管理（Warm/Cold/Deleteフェーズへ移行）することを強く推奨。
*   これにより、パフォーマンスの維持とストレージコストの最適化が可能。

## 8. 監視とアラート

### 8.1 Grafana ダッシュボード例

*   **FR時系列グラフ**: シンボル別、取引所別にFRの推移を表示。
*   **FR比較**: 主要シンボルのFRを取引所間で横比較。
*   **乖離率 (Basis)**: 計算された乖離率の時系列グラフ。
*   **異常検知**: `isAnomaly=true` のデータの発生頻度、該当シンボル/取引所の表示。
*   **システムメトリクス**: Kafkaのラグ、スループット、Collector/ProcessorのCPU/メモリ使用率、Elasticsearchのクエリパフォーマンスなど。

**サンプルクエリ (Grafana - Elasticsearch)**:

*   Binance BTCUSDTのFR推移:
    *   Query: `exchange:"Binance" AND symbol:"BTCUSDT"`
    *   Metrics: Average of `fundingRate`
    *   Group by: Date Histogram on `fundingTime`

### 8.2 アラート設定

*   **Grafana Alerting**: Grafana内で直接アラートルールを設定可能。
    *   例: `fundingRate`の絶対値が0.5%を10分間超えた場合。
    *   例: `isAnomaly`がtrueになった場合。
*   **Alertmanager連携**: GrafanaアラートをAlertmanagerに送信し、グルーピング、抑制、多様な通知チャネル（Slack, PagerDuty, Emailなど）へのルーティングを行う。
*   **Kafkaベース**: `fr-anomalies`トピックを直接監視する専用コンシューマーを作成し、通知ロジックを実装することも可能。

## 9. コーディング規約とベストプラクティス

*   **言語規約**: PythonはPEP 8、Java/Scalaは標準的なスタイルガイドに従う。
*   **ロギング**: 構造化ロギング（JSON形式など）を採用し、ログレベルを適切に設定。重要な処理の開始/終了、エラー発生箇所、主要なパラメータを記録。
*   **設定管理**: 設定値（APIキー、Kafkaブローカーアドレス、閾値など）はコードから分離し、環境変数、設定ファイル、または設定管理システムで管理。
*   **エラーハンドリング**: 予期せぬエラー（ネットワーク、データ形式、外部サービス障害など）を考慮し、適切な例外処理と回復メカニズム（リトライ、スキップ、アラート）を実装。
*   **テスト**:
    *   **ユニットテスト**: 各関数、クラスのロジックを検証。
    *   **インテグレーションテスト**: コンポーネント間の連携（API取得→Kafka送信、Kafka→Processor→Kafka、Kafka→ES）を検証。`testcontainers`などのライブラリが有効。
    *   **E2Eテスト**: 実際のデータフローに近い形でシステム全体の動作を確認。
*   **バージョン管理**: Gitを使用し、フィーチャーブランチ、コードレビュー、マージ戦略を確立。

## 10. デプロイメントと運用

### 10.1 デプロイメント

*   **コンテナ化**: 各コンポーネント（Collector, Processor, Kafka Connectなど）をDockerイメージとしてビルド。
*   **オーケストレーション**: Docker Compose（開発・小規模環境）またはKubernetes（本番・大規模環境）を使用してコンテナをデプロイ・管理。
*   **CI/CD**: GitHub Actions, GitLab CI, Jenkinsなどを使用して、ビルド、テスト、デプロイの自動化パイプラインを構築。

### 10.2 運用

*   **起動/停止**: オーケストレーションツールのコマンドで管理。
*   **設定変更**: 環境変数や設定ファイルを更新し、コンテナを再起動（ローリングアップデート推奨）。
*   **モニタリング**: Grafanaダッシュボードとアラート設定でシステム状態を常時監視。
*   **ログ管理**: Fluentd, Logstashなどでログを集約し、Elasticsearch等で分析・検索可能にする。
*   **バックアップ**: Kafkaのデータはレプリケーションで保護されるが、設定情報やステートストア（Kafka Streams/Flink）、Elasticsearchのスナップショットは別途バックアップ計画が必要。
*   **アップグレード**: Kafkaクラスタや他のコンポーネントのアップグレードは、互換性を確認し、ローリングアップデート手順に従って実施。**特にKafka 2.3.0.6からの移行は計画的に行う必要がある。**

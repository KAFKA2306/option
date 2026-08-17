# Finance Option Project

[![Browser scenario contract](https://github.com/KAFKA2306/option/actions/workflows/browser-scenario.yml/badge.svg)](https://github.com/KAFKA2306/option/actions/workflows/browser-scenario.yml)
[![Carry monitor contract](https://github.com/KAFKA2306/option/actions/workflows/carry-monitor.yml/badge.svg)](https://github.com/KAFKA2306/option/actions/workflows/carry-monitor.yml)

Bitcoin現物とBinance USDⓈ-M先物の価格関係を分析するprojectです。先物contractのmetadataを計算境界に含め、**無期限先物のpremium・funding**と、**受渡先物のbasis**を別の指標として扱います。

公開report: https://kafka2306.github.io/option/

> 公開reportは生成物です。常に最新・正常であることはREADMEだけでは保証しません。計算契約の正準はsource codeと回帰testです。

## 現在できること

- Binanceの現物・先物market dataを取得する
- contract type、status、上場日、delivery date、underlying typeを保持する
- 無期限先物のpremiumとfundingを計算する
- 受渡先物を実際の残存日数で年率換算する
- kline intervalに応じてvolatilityの年率換算係数を変える
- 未知・欠落したcontract typeをfail closedで拒否する
- 回帰testで主要な金融計算境界を確認する

## contract-aware計算方針

collectorはBinance futures exchange informationから次を保持します。

```text
symbol
contractType
status
onboardDate
deliveryDate
underlyingType
```

contract typeが不明または欠落している場合は、推測で計算せず処理を失敗させます。

### 無期限先物

`PERPETUAL`等の無期限contractでは、次を出力します。

```text
perpetual_premium_pct = (perpetual_price / spot_price - 1) × 100
funding_rate
funding_time
funding_interval_hours
funding_annualized_simple_pct
```

無期限先物には固定満期がないため、`days_to_maturity`と`annualized_basis`は欠損のままにします。架空の30日満期は仮定しません。

fundingの年率換算は、観測したfunding timestamp間隔に基づく単純projectionです。受渡先物basisとは別名・別列で保持します。

### 受渡先物

対応するdelivery contractでは、各観測時点の実残存日数を使用します。

```text
DTE(t) = delivery_datetime - observation_datetime

simple_annualized_basis(t)
  = (futures_price(t) / spot_price(t) - 1)
  × 365 / DTE(t)
  × 100
```

満期時点以降の観測は拒否します。出力には次を保存します。

```text
delivery_datetime
days_to_maturity
annualization_day_count
annualization_method
```

### volatilityの年率換算

volatilityは実際のkline intervalと365日crypto trading yearを使います。

```text
1m -> 525,600 periods/year
1h -> 8,760 periods/year
1d -> 365 periods/year
1w -> 365 / 7 periods/year
1M -> 12 periods/year
```

minute、hourly、weekly、monthly dataへ固定の`sqrt(252)`を適用しません。

## 主な構成

| パス | 役割 |
|---|---|
| `src/main.py` | pipeline entry point |
| `src/data_loader.py` | spot・futures data、contract metadata、funding historyの取得 |
| `src/analysis.py` | 分析処理の統合 |
| `src/contract_analysis.py` | contract-aware basisと年率換算の境界 |
| `src/advanced_analysis.py` | 共通統計分析とplot |
| `tests/test_contract_analysis.py` | 金融計算の回帰test |
| `index.html` | 生成済みreport |
| `output/` | 生成data・plot |

## 依存関係

主な依存は次のとおりです。

- pandas
- numpy
- python-binance
- pyarrowまたはfastparquet
- matplotlib
- scikit-learn
- seaborn
- jinja2

```bash
pip install -r requirements.txt
```

依存version、外部API、Binance側schemaが変わる可能性があります。clean environmentでの再現性はCI結果とlock fileの有無を別途確認してください。

## 実行

必要な場合は環境変数を設定します。

```text
BINANCE_API_KEY
BINANCE_API_SECRET
```

その後、repository rootから実行します。

```bash
python src/main.py
```

public market-data endpointを利用する処理でも、rate limit、地域・account制約、API変更、symbol停止等により失敗する可能性があります。API keyをrepository、log、Notebook出力へ保存しないでください。

## 検証

```bash
python -m unittest discover -s tests -v
```

`tests/test_contract_analysis.py`では次を確認します。

- 無期限先物ではpremiumを計算し、架空のannualized basisを作らない
- delivery contractの5日・30日・90日DTE
- delivery時点以降の観測を拒否する
- funding intervalをtimestampから推定する
- interval別のvolatility年率換算
- 未知contract typeをfail closedで拒否する

## 正準dataと生成物

source codeとtestは計算契約を示します。`index.html`と`output/`は、ある時点のdata・設定・codeから生成されたartifactです。生成物を最新reportとして扱うには、少なくとも次を確認してください。

- data as-of
- source symbolとcontract type
- observation timeとtimezone
- code commit
- API取得成功と欠損状態
- report生成時の設定

## 既知の制約

- market dataの正確性・完全性は外部APIに依存します
- simple annualizationは複利、funding変動、取引cost、margin、liquidation riskを表しません
- spotとfuturesのtimestamp整合が崩れるとbasisも不正確になります
- 過去のpremium、funding、basisは将来のreturnを保証しません
- 生成結果は投資助言や売買signalではありません

## セキュリティ

- API keyとsecretをcommitしない
- `.env`を使う場合は`.gitignore`へ追加する
- read-onlyで足りる処理に取引権限を付与しない
- 漏えいの可能性があるcredentialはprovider側で失効・再発行する

**README監査日:** 2026-08-05
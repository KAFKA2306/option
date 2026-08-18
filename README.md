# Bitcoin Derivatives Market Structure

[![Bitcoin derivatives evidence](https://github.com/KAFKA2306/option/actions/workflows/bitcoin-derivatives.yml/badge.svg)](https://github.com/KAFKA2306/option/actions/workflows/bitcoin-derivatives.yml)
[![Carry monitor contract](https://github.com/KAFKA2306/option/actions/workflows/carry-monitor.yml/badge.svg)](https://github.com/KAFKA2306/option/actions/workflows/carry-monitor.yml)

Bitcoin現物とBinance USDⓈ-M derivativesを、**raw evidenceから再生成できる時系列dataset**として保存するrepositoryです。reportやplotより、`api/v1/bitcoin-derivatives/` を正準成果物として扱います。

## 正準data

- [dataset index](api/v1/bitcoin-derivatives/index.json)
- [current market structure](api/v1/bitcoin-derivatives/current.json)
- [daily observations](api/v1/bitcoin-derivatives/daily.json)
- [funding events](api/v1/bitcoin-derivatives/funding.json)
- [open interest](api/v1/bitcoin-derivatives/open-interest.json)
- [term structure](api/v1/bitcoin-derivatives/term-structure.json)
- [latest raw manifest](data/derivatives/raw/latest-manifest.json)
- [contract metadata history](data/derivatives/metadata-history.json)

`Bitcoin derivatives evidence` workflowが毎日一次情報を取得し、raw responseをSHA-256でcontent-addressed保存した後、上記APIを生成します。CIでは同じraw evidenceだけからoffline再生成し、live生成物と差分がないことを検証します。

## 計算境界

### PERPETUAL

無期限先物では次を保持します。

- spot / contract / mark / index price
- perpetual premium
- mark-index premium
- funding rate / funding timestamp
- open interest
- volume / quote volume
- best bid / ask

固定満期を仮定しないため、`days_to_maturity` と delivery basis は `null` です。

### Delivery futures

受渡先物では実際の `deliveryDate` からDTEを計算し、次を保持します。

```text
delivery_basis_pct = (futures_price / spot_price - 1) × 100
annualized_delivery_basis_pct = delivery_basis_pct × 365 / DTE
```

funding / perpetual premiumは `null` です。満期後のcontractや未知のactive `contractType` は成功値で埋めず、処理を失敗させます。

## Source contract

collector: [`src/collect_market_structure.py`](src/collect_market_structure.py)

data path:

```text
Binance public market data
  ↓
data/derivatives/raw/objects/<sha256>.json
  ↓
data/derivatives/raw/latest-manifest.json
  ↓
api/v1/bitcoin-derivatives/*.json
```

各raw objectはsource URLとSHA-256をmanifestに保持します。API schema drift、symbol停止、空response、unknown contract type、raw hash不一致はfail closedです。

Open Interest Statisticsの履歴取得範囲はBinance側の公開範囲に従い、取得不能な過去値を推測・forward fillしません。この制約は`open-interest.json`にも明示します。

## 実行

public market-dataのみを使うため、このcollectorにAPI keyは不要です。

```bash
python src/collect_market_structure.py
```

保存済みraw evidenceから再生成する場合:

```bash
python src/collect_market_structure.py --offline
```

検証:

```bash
python -m unittest -v tests.test_market_structure_collector
```

## Legacy analysis

`index.html`、`output/`、既存のplot/report pipelineは過去の探索・可視化資産です。現在値や正準datasetとしては使用しません。公開reportは補助surfaceです: https://kafka2306.github.io/option/

投資助言・売買signalを提供するrepositoryではありません。

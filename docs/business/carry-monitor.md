# Funding / Basis Carry Monitor

## 対象

BTC現物と暗号資産デリバティブを同時に確認する運用・risk/research・treasury担当向けの監査可能なmonitorです。取引執行、売買推奨、将来収益や裁定利益の保証は提供しません。

## データ契約

`config/watchlists/*.json` の `carry-watchlist.v1` をcode変更なしで差し替え、`src/carry_monitor.py` が既存のcontract-aware analysis parquetから `carry-monitor.v1` JSON/HTMLを生成します。

- PERPETUAL系: premium、funding、simple annualized funding projectionだけを扱い、DTEやdelivery basisを生成しません。
- delivery系: 実際のdelivery datetimeと正のDTEがある場合だけdelivery basisを扱います。
- watchlistのexpected contract typeとsnapshot metadataが不一致なら `REJECTED` です。
- 欠損値は `NOT_COMPUTABLE` または明示的なrejection reasonとして残します。
- 前回monitorを`--previous`で渡すと同一watch IDの差分を決定論的に生成します。
- provenanceにはsource endpoint/symbol、retrieved_at、contract metadata、calculation revision、commit SHAを保存します。
- credential風field (`api_key`, `secret`, `token`, `password`等) はwatchlist/inputでfail-closeします。

## 生成例

```bash
python src/carry_monitor.py \
  --analysis-parquet output/analysis/advanced_basis_data_1day.parquet \
  --watchlist config/watchlists/btc-sample.json \
  --output-json output/carry-monitor.json \
  --output-html output/carry-monitor.html \
  --retrieved-at 2026-08-10T08:00:00Z \
  --commit-sha "$(git rev-parse HEAD)"
```

`retrieved_at`は実際の取得run時刻を明示して渡します。過去snapshotへ現在時刻を後付けしてはいけません。

## 無料sample / 有償PoC

無料sampleは公開BTC watchlist 1件と単発snapshotを想定します。有償PoCは顧客が指定する3〜10 contract、顧客別threshold、4週間の定期briefを検証対象とします。API credentialや個人情報をwatchlist/reportへ保存しません。

CTA候補は `サンプルmonitorを見る`、`自社watchlistを相談する`、`4週間PoCを相談する` です。営業・相談・契約実績は、実際の証拠がある場合だけKPI台帳へ記録します。

## 計測イベント

`sample_monitor_opened`、`watchlist_example_opened`、`business_inquiry_started`、`qualified_inquiry`、`pilot_booked`、`paid_pilot`を別イベントとして扱います。現時点で実計測がないイベントを発生済みとして記録しません。

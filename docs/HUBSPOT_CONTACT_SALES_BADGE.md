# HubSpot コンタクト販売バッジ更新バッチ

## 概要

`scripts/update_contact_sales_badge.py` は、HubSpot の販売パイプラインに紐づく取引を集計し、コンタクトのカスタムプロパティ（契約数 / 買付取得数 / 調査検討数 / 資料開示数）を自動更新するバッチです。

更新対象プロパティ:

| HubSpotプロパティ | 内容 |
| --- | --- |
| `contact_contracts` | 契約数 |
| `contact_purchases` | 買付取得数 |
| `contact_surveys_considered` | 調査検討数 |
| `contact_documents_disclosed` | 資料開示数 |

## カウントルール

販売パイプライン内の各取引のステージラベルに応じて以下のルールで加算されます（1取引あたり +1）:

| ステージ | 加算されるプロパティ |
| --- | --- |
| 「契約」または「決済」(Contract / Settlement) | 契約数 / 買付取得数 / 調査検討数 / 資料開示数 |
| 「見込み角度A」「見込み角度B」「買付取得」等 | 買付取得数 / 調査検討数 / 資料開示数 |
| 「調査/検討」(Survey / Review) | 調査検討数 / 資料開示数 |
| 「資料開示」(Disclosure) | 資料開示数 |

※ステージラベルには日本語・英語の両方をサポートするキーワード判定を実装しています。

## 前提条件

- HubSpot API キーが `.env` もしくは環境変数に設定済み
- 販売パイプラインIDが `HUBSPOT_SALES_PIPELINE_ID` に設定済み（既定値: `682910274`）
- mirai-api がセットアップ済み (`venv` / 依存ライブラリ導入済み)

## 実行方法

```bash
cd /var/www/mirai-api
source venv/bin/activate
python3 scripts/update_contact_sales_badge.py
```

### systemd タイマー（毎日 04:00 実行）

```bash
sudo cp contact-sales-badge.service /etc/systemd/system/
sudo cp contact-sales-badge.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable contact-sales-badge.timer
sudo systemctl start contact-sales-badge.timer

# 確認
sudo systemctl status contact-sales-badge.timer
sudo systemctl list-timers contact-sales-badge.timer
```

## ログ

- 標準出力、および `/var/www/mirai-api/logs/contact_sales_badge.log` に記録されます。

## 環境変数

| 変数名 | 説明 | 既定値 |
| --- | --- | --- |
| `HUBSPOT_SALES_PIPELINE_ID` | 販売パイプラインID | `682910274` |
| `HUBSPOT_SALES_BATCH_LIMIT` | HubSpot検索時の1ページ取得件数 | `100` |
| `HUBSPOT_CONTACT_UPDATE_DELAY` | 連続更新のウェイト秒数 | `0.2` |

## 今後の拡張ヒント

- systemd サービス / タイマーを作成し、定期実行
- ステージキーワードを環境変数化して柔軟に変更
- コンタクトが0件になった場合のリセットロジック追加


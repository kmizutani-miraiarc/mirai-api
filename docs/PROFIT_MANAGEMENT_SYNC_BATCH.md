# 粗利按分管理データ同期バッチ

## 概要

このバッチスクリプトは、HubSpotから粗利按分管理データを自動的に取り込みます。

## 実行タイミング

1日1回、午前2時に自動実行されます。

## 取り込み条件

- 販売取引の決済日（settlement_date）が入力されている物件情報を対象に取り込みます。

## 取り込むデータ

### 基本情報
- **物件番号**: HubSpotの物件情報のID
- **物件名**: HubSpotの物件情報の物件名
- **種別**: 空欄

### 仕入情報
- **仕入決済日**: 物件情報に紐づく取引の仕入パイプラインの決済日（settlement_date）
- **仕入価格**: 物件情報に紐づく取引の仕入パイプラインの仕入価格（research_purchase_price）

### 販売情報
- **販売決済日**: 物件情報に紐づく取引の販売パイプラインの決済日（settlement_date）
- **販売価格**: 物件情報に紐づく取引の販売パイプラインの販売価格（sales_sales_price）

### 粗利情報
- **粗利**: 空欄
- **粗利確定フラグ**: OFF

### 担当者情報
- **仕入担当者**: 物件情報に紐づく取引の仕入パイプラインの取引担当者（hubspot_owner_id）
- **仕入担当者の粗利率、粗利額**: 空欄
- **販売担当者**: 物件情報に紐づく取引の販売パイプラインの取引担当者（hubspot_owner_id）
- **販売担当者の粗利率、粗利額**: 空欄

### 計上年月
- **計上年月**: 物件情報に紐づく取引の販売パイプラインの決済日（settlement_date）の年月

## ファイル

- **スクリプト**: `mirai-api/scripts/sync_profit_management.py`
- **ログファイル**: `/var/www/mirai-api/logs/profit_management_sync.log`

## 手動実行

```bash
cd /var/www/mirai-api
python3 scripts/sync_profit_management.py
```

## crontab設定

以下のコマンドでcrontabに追加してください：

```bash
crontab -e
```

以下の行を追加：

```
0 2 * * * cd /var/www/mirai-api && /usr/bin/python3 scripts/sync_profit_management.py >> /var/www/mirai-api/logs/profit_management_sync_cron.log 2>&1
```

または、既存のcrontabに追加する場合：

```bash
(crontab -l 2>/dev/null; echo "0 2 * * * cd /var/www/mirai-api && /usr/bin/python3 scripts/sync_profit_management.py >> /var/www/mirai-api/logs/profit_management_sync_cron.log 2>&1") | crontab -
```

## 注意事項

- HubSpot APIのレート制限に注意してください
- ログファイルは定期的に確認してください
- エラーが発生した場合は、ログファイルを確認して原因を特定してください



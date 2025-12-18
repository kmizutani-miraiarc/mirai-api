# 粗利按分管理データ同期バッチ

## 概要

このバッチスクリプトは、HubSpotから粗利按分管理データを自動的に取り込みます。

## 実行タイミング

1日1回、午前2時に自動実行されます（systemdタイマーを使用）。

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

### 方法1: systemdサービスとして実行（推奨）

```bash
# systemdサービスとして実行
sudo systemctl start profit-management-sync.service

# ログを確認
sudo journalctl -u profit-management-sync.service -f
```

### 方法2: 直接Pythonスクリプトを実行

```bash
cd /var/www/mirai-api
sudo -u mirai-api /var/www/mirai-api/venv/bin/python3 /var/www/mirai-api/scripts/sync_profit_management.py
```

## systemdタイマーの設定

### サービスとタイマーファイルの配置

```bash
# サービスファイルをコピー
sudo cp profit-management-sync.service /etc/systemd/system/
sudo cp profit-management-sync.timer /etc/systemd/system/

# systemdの設定をリロード
sudo systemctl daemon-reload

# タイマーを有効化
sudo systemctl enable profit-management-sync.timer
sudo systemctl start profit-management-sync.timer
```

### タイマーの状態確認

```bash
# タイマーの状態を確認
systemctl status profit-management-sync.timer

# 次回実行時刻を確認
systemctl list-timers profit-management-sync.timer
```

### タイマーの無効化（必要に応じて）

```bash
# タイマーを停止・無効化
sudo systemctl stop profit-management-sync.timer
sudo systemctl disable profit-management-sync.timer
```

## 旧crontab設定からの移行

以前crontabで設定していた場合は、以下の手順で移行してください：

1. **crontabの設定を確認**
```bash
crontab -l | grep sync_profit_management
```

2. **crontabから削除**
```bash
crontab -e
# 該当行を削除
```

3. **systemdタイマーを設定**（上記の「systemdタイマーの設定」を参照）

## 注意事項

- HubSpot APIのレート制限に注意してください
- ログファイルは定期的に確認してください
- エラーが発生した場合は、ログファイルを確認して原因を特定してください





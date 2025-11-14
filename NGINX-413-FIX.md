# 413エラー（Request Entity Too Large）の解決方法

## 問題
nginxから413エラーが返されています。これはnginxの`client_max_body_size`設定が正しく適用されていないことを示しています。

## FastAPI/Uvicorn側の制限
**FastAPI/Uvicorn側にはファイルサイズ制限はありません。** Starletteのデフォルトでは制限はありません。

問題は完全にnginx側の設定です。

## 解決手順

### 1. 実際に使用されているnginx設定を確認

```bash
# 実際に適用されている設定を確認
sudo nginx -T | grep -A 10 -B 10 client_max_body_size

# すべてのnginx設定ファイルを確認
sudo nginx -T
```

### 2. 使用されているパスを確認

エラーログから、どのパスでアクセスしているか確認：
- `/api/satei/upload` の場合 → `location /api/` ブロックが必要
- `/satei/upload` の場合 → `location /` ブロックが必要

### 3. nginx設定ファイルの確認

使用されているnginx設定ファイルを確認：
```bash
# メイン設定ファイル
cat /etc/nginx/nginx.conf

# 設定ファイルの読み込み順序
ls -la /etc/nginx/conf.d/
ls -la /etc/nginx/sites-enabled/
```

### 4. 正しい設定の確認

**すべてのlocationブロックで`client_max_body_size 200M;`が設定されている必要があります：**

```nginx
http {
    # グローバル設定（デフォルト値）
    client_max_body_size 200M;
    
    server {
        # サーバーレベル設定（推奨）
        client_max_body_size 200M;
        
        location /api/ {
            # locationレベル設定（最優先）
            client_max_body_size 200M;
            
            proxy_pass http://mirai_api/;
            # ... その他の設定
        }
        
        location / {
            # すべてのlocationブロックで設定
            client_max_body_size 200M;
            
            proxy_pass http://mirai_api;
            # ... その他の設定
        }
    }
}
```

### 5. nginx設定の再読み込み

```bash
# 構文チェック
sudo nginx -t

# 問題がなければ再読み込み
sudo systemctl reload nginx
# または
sudo nginx -s reload
```

### 6. 実際の設定を確認

再読み込み後、実際に適用されている設定を確認：
```bash
sudo nginx -T | grep -A 5 -B 5 "location.*satei\|client_max_body_size"
```

## よくある問題

### 問題1: デフォルトの1Mが適用されている

nginxのデフォルトは`client_max_body_size 1m;`です。設定ファイルに明示的に設定されていない場合、この値が適用されます。

**解決方法**: すべてのlocationブロックで`client_max_body_size 200M;`を設定

### 問題2: 別のnginx設定ファイルが優先されている

複数の設定ファイルがある場合、優先順位が問題になることがあります。

**解決方法**: 
```bash
# すべての設定ファイルを確認
sudo nginx -T

# 実際に適用されている設定を確認
sudo nginx -T | grep client_max_body_size
```

### 問題3: パスが一致していない

`/api/satei/upload`にアクセスしている場合、`location /api/`ブロックが必要です。

**解決方法**: アクセスしているパスに一致するlocationブロックを確認

### 問題4: nginxが再読み込みされていない

設定を変更したが、nginxを再読み込みしていない場合。

**解決方法**: `sudo systemctl reload nginx`を実行

## 確認用コマンド

```bash
# 1. nginx設定の構文チェック
sudo nginx -t

# 2. 実際に適用されている設定を確認
sudo nginx -T | grep -A 20 "location.*/" | grep -A 10 client_max_body_size

# 3. nginxエラーログを確認
sudo tail -f /var/log/nginx/error.log

# 4. nginxアクセスログを確認
sudo tail -f /var/log/nginx/access.log
```

## テスト方法

設定を変更した後、テストリクエストを送信：

```bash
# 小さなファイルでテスト（1MB）
dd if=/dev/zero of=test_file.bin bs=1M count=1

# curlでテスト
curl -X POST \
  -H "X-API-Key: YOUR_API_KEY" \
  -F "email=test@example.com" \
  -F "files=@test_file.bin" \
  https://your-domain.com/api/satei/upload
```

## 重要な注意事項

1. **nginx設定を変更した後は必ず`nginx -t`で構文チェック**
2. **問題がなければ`systemctl reload nginx`で再読み込み**
3. **すべてのlocationブロックで`client_max_body_size`を設定**
4. **グローバル、サーバー、locationすべてのレベルで設定することを推奨**



# Mirai API Node.js サンプル

Mirai API 物件検索をNode.jsから呼び出すサンプルコードです。

## ファイル構成

- `axios-basic-example.js` - 最もシンプルなaxiosサンプル
- `axios-simple-example.js` - 基本的なaxiosサンプル
- `axios-practical-example.js` - 実用的なaxiosサンプル（クラス使用）
- `nodejs-bukken-search.js` - 基本的なAPI呼び出しサンプル
- `express-bukken-app.js` - Express.jsアプリケーションサンプル
- `package.json` - 依存関係とスクリプト設定
- `env.example` - 環境変数設定例

## 認証について

**重要**: このAPIは認証が必要です。すべてのリクエストに`X-API-Key`ヘッダーを含める必要があります。

### APIキーの設定

1. **環境変数での設定**（推奨）:
   ```bash
   export MIRAI_API_KEY="your-actual-api-key"
   ```

2. **コード内での直接設定**:
   ```javascript
   const API_KEY = 'your-actual-api-key';
   ```

### 認証エラー

- **401 Unauthorized**: APIキーが未提供または無効
- **エラーメッセージ**: `"API key is required"` または `"Invalid API key"`

## セットアップ

### 1. 依存関係のインストール

```bash
npm install
```

### 2. 環境変数の設定

```bash
# 環境変数ファイルをコピー
cp env.example .env

# 環境変数を編集
nano .env
```

`.env`ファイルの内容：
```bash
MIRAI_API_BASE_URL=https://api.miraiarc.co.jp
MIRAI_API_KEY=your-mirai-api-key-here
PORT=3000
NODE_ENV=development
```

## 使用方法

### 基本的なAPI呼び出し

```bash
# 最もシンプルなaxiosサンプル
npm run axios-basic

# 基本的なaxiosサンプル
npm run axios-simple

# 実用的なaxiosサンプル（クラス使用）
npm run axios-practical

# 物件検索のテスト実行
npm run test

# または直接実行
node axios-basic-example.js
node axios-simple-example.js
node axios-practical-example.js
```

### Express.jsアプリケーション

```bash
# 開発モードで起動
npm run dev

# 本番モードで起動
npm start
```

アプリケーション起動後：
- ヘルスチェック: http://localhost:3000/health
- API情報: http://localhost:3000/api/info

## API エンドポイント

### 物件検索

```bash
curl -X POST http://localhost:3000/api/bukken/search \
  -H "Content-Type: application/json" \
  -d '{
    "bukken_name": "マンション",
    "bukken_state": "東京都",
    "bukken_city": "渋谷区",
    "limit": 10
  }'
```

### 物件詳細取得

```bash
curl http://localhost:3000/api/bukken/{bukken_id}
```

### 物件作成

```bash
curl -X POST http://localhost:3000/api/bukken \
  -H "Content-Type: application/json" \
  -d '{
    "bukken_name": "テスト物件",
    "bukken_state": "東京都",
    "bukken_city": "渋谷区",
    "bukken_address": "渋谷区渋谷1-1-1"
  }'
```

### 物件更新

```bash
curl -X PATCH http://localhost:3000/api/bukken/{bukken_id} \
  -H "Content-Type: application/json" \
  -d '{
    "bukken_name": "更新された物件名",
    "bukken_address": "渋谷区渋谷1-1-2"
  }'
```

### 物件削除

```bash
curl -X DELETE http://localhost:3000/api/bukken/{bukken_id}
```

## コード例

### 最もシンプルなaxiosサンプル

```javascript
const axios = require('axios');

async function searchBukken() {
    try {
        const response = await axios.post('https://api.miraiarc.co.jp/hubspot/bukken/search', {
            bukken_name: 'マンション',
            bukken_state: '東京都',
            bukken_city: '渋谷区',
            limit: 5
        }, {
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'your-mirai-api-key-here'  // 実際のAPIキーに変更
            }
        });

        console.log('検索結果:', response.data);
        return response.data;
    } catch (error) {
        console.error('エラー:', error.message);
    }
}

searchBukken();
```

### クラスを使った実用的なサンプル

```javascript
const axios = require('axios');

class BukkenAPI {
    constructor() {
        this.client = axios.create({
            baseURL: 'https://api.miraiarc.co.jp',
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': 'your-mirai-api-key-here'  // 実際のAPIキーに変更
            }
        });
    }

    async search(params = {}) {
        const response = await this.client.post('/hubspot/bukken/search', {
            bukken_name: params.name || '',
            bukken_state: params.state || '',
            bukken_city: params.city || '',
            limit: params.limit || 10
        });
        return response.data;
    }
}

// 使用例
const api = new BukkenAPI();
api.search({ name: 'マンション', state: '東京都' });
```

### 条件付き検索

```javascript
// 物件名で部分一致検索
const nameResults = await searchBukken({
    bukken_name: 'マンション'
});

// 都道府県で完全一致検索
const stateResults = await searchBukken({
    bukken_state: '東京都'
});

// 市区町村で完全一致検索
const cityResults = await searchBukken({
    bukken_city: '渋谷区'
});

// 複数条件で検索
const multiResults = await searchBukken({
    bukken_state: '東京都',
    bukken_city: '渋谷区',
    bukken_name: 'マンション',
    limit: 5
});
```

### ページネーション

```javascript
// 最初のページ
const firstPage = await searchBukken({
    limit: 10
});

// 次のページ（afterパラメータを使用）
const nextPage = await searchBukken({
    limit: 10,
    after: firstPage.paging.next.after
});
```

### ソート設定

```javascript
const sortedResults = await searchBukken({
    sorts: [
        {
            "propertyName": "bukken_name",
            "direction": "ASCENDING"
        },
        {
            "propertyName": "createdate",
            "direction": "DESCENDING"
        }
    ]
});
```

## エラーハンドリング

```javascript
try {
    const result = await searchBukken();
    console.log('成功:', result);
} catch (error) {
    if (error.response) {
        // APIエラー
        console.error('ステータス:', error.response.status);
        console.error('エラー詳細:', error.response.data);
    } else if (error.request) {
        // ネットワークエラー
        console.error('リクエストエラー:', error.request);
    } else {
        // その他のエラー
        console.error('エラー:', error.message);
    }
}
```

## 注意事項

1. **APIキー**: 実際のAPIキーに変更してください
2. **ドメイン**: 実際のAPIドメインに変更してください
3. **認証**: 必要に応じて認証方式を調整してください
4. **タイムアウト**: ネットワーク状況に応じてタイムアウト値を調整してください
5. **エラーハンドリング**: 本番環境では適切なエラーハンドリングを実装してください

## トラブルシューティング

### よくあるエラー

1. **401 Unauthorized**: APIキーが正しく設定されていない
2. **404 Not Found**: エンドポイントURLが間違っている
3. **500 Internal Server Error**: サーバー側のエラー
4. **Timeout**: ネットワーク接続の問題

### デバッグ方法

```javascript
// リクエストの詳細をログ出力
console.log('リクエストURL:', url);
console.log('リクエストヘッダー:', headers);
console.log('リクエストボディ:', data);

// レスポンスの詳細をログ出力
console.log('レスポンスステータス:', response.status);
console.log('レスポンスヘッダー:', response.headers);
console.log('レスポンスボディ:', response.data);
```

## ライセンス

MIT License

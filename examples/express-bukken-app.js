// Express.js アプリケーションでの Mirai API 物件検索サンプル
// 必要なパッケージ: npm install express axios cors dotenv

const express = require('express');
const axios = require('axios');
const cors = require('cors');
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3000;

// ミドルウェア
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// API設定
const MIRAI_API_BASE_URL = process.env.MIRAI_API_BASE_URL || 'https://api.miraiarc.co.jp';
const MIRAI_API_KEY = process.env.MIRAI_API_KEY || 'your-mirai-api-key-here';

// Mirai API呼び出し用のヘルパー関数
async function callMiraiAPI(endpoint, method = 'GET', data = null) {
    try {
        const config = {
            method,
            url: `${MIRAI_API_BASE_URL}${endpoint}`,
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': MIRAI_API_KEY
            },
            timeout: 30000
        };

        if (data) {
            config.data = data;
        }

        const response = await axios(config);
        return response.data;
    } catch (error) {
        console.error('Mirai API呼び出しエラー:', error.message);
        throw error;
    }
}

// ルート: 物件検索
app.post('/api/bukken/search', async (req, res) => {
    try {
        console.log('物件検索リクエスト:', req.body);

        const searchParams = {
            bukken_name: req.body.bukken_name || '',
            bukken_state: req.body.bukken_state || '',
            bukken_city: req.body.bukken_city || '',
            query: req.body.query || '',
            after: req.body.after || '',
            limit: req.body.limit || 10,
            sorts: req.body.sorts || [
                {
                    "propertyName": "createdate",
                    "direction": "DESCENDING"
                }
            ],
            properties: req.body.properties || [
                "bukken_name",
                "bukken_state",
                "bukken_city",
                "bukken_address"
            ]
        };

        const result = await callMiraiAPI('/hubspot/bukken/search', 'POST', searchParams);

        res.json({
            success: true,
            data: result,
            message: '物件検索が完了しました'
        });

    } catch (error) {
        console.error('物件検索エラー:', error.message);
        res.status(500).json({
            success: false,
            error: error.message,
            message: '物件検索でエラーが発生しました'
        });
    }
});

// ルート: 物件詳細取得
app.get('/api/bukken/:id', async (req, res) => {
    try {
        const bukkenId = req.params.id;
        console.log('物件詳細取得リクエスト:', bukkenId);

        const result = await callMiraiAPI(`/hubspot/bukken/${bukkenId}`, 'GET');

        res.json({
            success: true,
            data: result,
            message: '物件詳細を取得しました'
        });

    } catch (error) {
        console.error('物件詳細取得エラー:', error.message);
        res.status(500).json({
            success: false,
            error: error.message,
            message: '物件詳細取得でエラーが発生しました'
        });
    }
});

// ルート: 物件作成
app.post('/api/bukken', async (req, res) => {
    try {
        console.log('物件作成リクエスト:', req.body);

        const bukkenData = {
            bukken_name: req.body.bukken_name,
            bukken_state: req.body.bukken_state,
            bukken_city: req.body.bukken_city,
            bukken_address: req.body.bukken_address
        };

        const result = await callMiraiAPI('/hubspot/bukken', 'POST', bukkenData);

        res.json({
            success: true,
            data: result,
            message: '物件を作成しました'
        });

    } catch (error) {
        console.error('物件作成エラー:', error.message);
        res.status(500).json({
            success: false,
            error: error.message,
            message: '物件作成でエラーが発生しました'
        });
    }
});

// ルート: 物件更新
app.patch('/api/bukken/:id', async (req, res) => {
    try {
        const bukkenId = req.params.id;
        console.log('物件更新リクエスト:', bukkenId, req.body);

        const result = await callMiraiAPI(`/hubspot/bukken/${bukkenId}`, 'PATCH', req.body);

        res.json({
            success: true,
            data: result,
            message: '物件を更新しました'
        });

    } catch (error) {
        console.error('物件更新エラー:', error.message);
        res.status(500).json({
            success: false,
            error: error.message,
            message: '物件更新でエラーが発生しました'
        });
    }
});

// ルート: 物件削除
app.delete('/api/bukken/:id', async (req, res) => {
    try {
        const bukkenId = req.params.id;
        console.log('物件削除リクエスト:', bukkenId);

        const result = await callMiraiAPI(`/hubspot/bukken/${bukkenId}`, 'DELETE');

        res.json({
            success: true,
            data: result,
            message: '物件を削除しました'
        });

    } catch (error) {
        console.error('物件削除エラー:', error.message);
        res.status(500).json({
            success: false,
            error: error.message,
            message: '物件削除でエラーが発生しました'
        });
    }
});

// ルート: ヘルスチェック
app.get('/health', (req, res) => {
    res.json({
        success: true,
        message: 'Express.js アプリケーションが正常に動作しています',
        timestamp: new Date().toISOString()
    });
});

// ルート: API情報
app.get('/api/info', (req, res) => {
    res.json({
        success: true,
        data: {
            name: 'Mirai API Express.js サンプル',
            version: '1.0.0',
            description: 'Mirai API 物件検索のExpress.jsサンプルアプリケーション',
            endpoints: [
                'POST /api/bukken/search - 物件検索',
                'GET /api/bukken/:id - 物件詳細取得',
                'POST /api/bukken - 物件作成',
                'PATCH /api/bukken/:id - 物件更新',
                'DELETE /api/bukken/:id - 物件削除',
                'GET /health - ヘルスチェック',
                'GET /api/info - API情報'
            ]
        }
    });
});

// エラーハンドリング
app.use((err, req, res, next) => {
    console.error('アプリケーションエラー:', err.message);
    res.status(500).json({
        success: false,
        error: err.message,
        message: 'サーバー内部エラーが発生しました'
    });
});

// 404ハンドリング
app.use((req, res) => {
    res.status(404).json({
        success: false,
        message: '指定されたエンドポイントが見つかりません'
    });
});

// サーバー起動
app.listen(PORT, () => {
    console.log(`Express.js サーバーが起動しました`);
    console.log(`ポート: ${PORT}`);
    console.log(`ヘルスチェック: http://localhost:${PORT}/health`);
    console.log(`API情報: http://localhost:${PORT}/api/info`);
});

module.exports = app;

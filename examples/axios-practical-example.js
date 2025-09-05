// axios を使った Mirai API 物件検索の実用的なサンプル
// 必要なパッケージ: npm install axios

const axios = require('axios');

// API設定
const API_BASE_URL = 'https://api.miraiarc.co.jp';
const API_KEY = 'your-mirai-api-key-here'; // 実際のAPIキーに変更

// 共通のaxios設定
const apiClient = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
        'Content-Type': 'application/json',
        'X-API-Key': API_KEY
    }
});

// エラーハンドリング用のインターセプター
apiClient.interceptors.response.use(
    response => response,
    error => {
        console.error('API呼び出しエラー:', error.message);
        if (error.response) {
            console.error('ステータス:', error.response.status);
            console.error('エラー詳細:', error.response.data);
        }
        return Promise.reject(error);
    }
);

// 物件検索クラス
class BukkenAPI {
    constructor() {
        this.client = apiClient;
    }

    // 物件検索
    async search(params = {}) {
        const searchData = {
            bukken_name: params.name || '',
            bukken_state: params.state || '',
            bukken_city: params.city || '',
            query: params.query || '',
            after: params.after || '',
            limit: params.limit || 10,
            sorts: params.sorts || [
                {
                    "propertyName": "createdate",
                    "direction": "DESCENDING"
                }
            ],
            properties: params.properties || [
                "bukken_name",
                "bukken_state",
                "bukken_city",
                "bukken_address"
            ]
        };

        const response = await this.client.post('/hubspot/bukken/search', searchData);
        return response.data;
    }

    // 物件詳細取得
    async getDetail(bukkenId) {
        const response = await this.client.get(`/hubspot/bukken/${bukkenId}`);
        return response.data;
    }

    // 物件作成
    async create(bukkenData) {
        const response = await this.client.post('/hubspot/bukken', bukkenData);
        return response.data;
    }

    // 物件更新
    async update(bukkenId, updateData) {
        const response = await this.client.patch(`/hubspot/bukken/${bukkenId}`, updateData);
        return response.data;
    }

    // 物件削除
    async delete(bukkenId) {
        const response = await this.client.delete(`/hubspot/bukken/${bukkenId}`);
        return response.data;
    }
}

// 使用例
async function examples() {
    const bukkenAPI = new BukkenAPI();

    try {
        // 1. 全件検索
        console.log('=== 全件検索 ===');
        const allResults = await bukkenAPI.search();
        console.log(`全件数: ${allResults.count}`);
        console.log(`取得件数: ${allResults.results.length}`);

        // 2. 条件付き検索
        console.log('\n=== 条件付き検索 ===');
        const filteredResults = await bukkenAPI.search({
            name: 'マンション',
            state: '東京都',
            city: '渋谷区',
            limit: 3
        });
        console.log(`条件付き検索結果: ${filteredResults.count}件`);

        // 3. 物件詳細取得
        if (allResults.results.length > 0) {
            console.log('\n=== 物件詳細取得 ===');
            const firstBukken = allResults.results[0];
            const detail = await bukkenAPI.getDetail(firstBukken.id);
            console.log('物件詳細:', detail.properties);
        }

        // 4. 物件作成
        console.log('\n=== 物件作成 ===');
        const newBukken = await bukkenAPI.create({
            bukken_name: 'テスト物件',
            bukken_state: '東京都',
            bukken_city: '渋谷区',
            bukken_address: '渋谷区渋谷1-1-1'
        });
        console.log('作成された物件ID:', newBukken.id);

        // 5. 物件更新
        console.log('\n=== 物件更新 ===');
        const updatedBukken = await bukkenAPI.update(newBukken.id, {
            bukken_name: '更新されたテスト物件',
            bukken_address: '渋谷区渋谷1-1-2'
        });
        console.log('更新された物件:', updatedBukken.properties);

        // 6. 物件削除
        console.log('\n=== 物件削除 ===');
        await bukkenAPI.delete(newBukken.id);
        console.log('物件を削除しました');

    } catch (error) {
        console.error('処理中にエラーが発生しました:', error.message);
    }
}

// ページネーション例
async function paginationExample() {
    const bukkenAPI = new BukkenAPI();
    
    try {
        console.log('=== ページネーション例 ===');
        
        // 最初のページ
        const firstPage = await bukkenAPI.search({ limit: 3 });
        console.log('1ページ目:', firstPage.results.length, '件');
        
        // 次のページ
        if (firstPage.paging && firstPage.paging.next) {
            const secondPage = await bukkenAPI.search({
                limit: 3,
                after: firstPage.paging.next.after
            });
            console.log('2ページ目:', secondPage.results.length, '件');
        }

    } catch (error) {
        console.error('ページネーション処理でエラー:', error.message);
    }
}

// 複数条件検索例
async function multiConditionExample() {
    const bukkenAPI = new BukkenAPI();
    
    try {
        console.log('=== 複数条件検索例 ===');
        
        // 物件名のみ
        const nameOnly = await bukkenAPI.search({ name: 'マンション' });
        console.log('物件名検索:', nameOnly.count, '件');
        
        // 都道府県のみ
        const stateOnly = await bukkenAPI.search({ state: '東京都' });
        console.log('都道府県検索:', stateOnly.count, '件');
        
        // 市区町村のみ
        const cityOnly = await bukkenAPI.search({ city: '渋谷区' });
        console.log('市区町村検索:', cityOnly.count, '件');
        
        // 複数条件
        const multiCondition = await bukkenAPI.search({
            name: 'マンション',
            state: '東京都',
            city: '渋谷区'
        });
        console.log('複数条件検索:', multiCondition.count, '件');

    } catch (error) {
        console.error('複数条件検索でエラー:', error.message);
    }
}

// メイン実行
async function main() {
    console.log('Mirai API 物件検索サンプルを開始します...\n');
    
    await examples();
    await paginationExample();
    await multiConditionExample();
    
    console.log('\nサンプル実行完了');
}

// 実行
if (require.main === module) {
    main();
}

// エクスポート
module.exports = {
    BukkenAPI,
    examples,
    paginationExample,
    multiConditionExample
};

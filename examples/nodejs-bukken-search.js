// Node.js から Mirai API 物件検索を呼び出すサンプル
// 必要なパッケージ: npm install axios

const axios = require('axios');

// API設定
const API_BASE_URL = 'https://api.miraiarc.co.jp'; // 実際のドメインに変更
const API_KEY = 'your-mirai-api-key-here'; // 実際のAPIキーに変更

// 物件検索のサンプル関数
async function searchBukken(searchParams = {}) {
    try {
        console.log('物件検索を開始します...');
        console.log('検索パラメータ:', searchParams);

        // API呼び出し
        const response = await axios.post(`${API_BASE_URL}/hubspot/bukken/search`, {
            // 検索パラメーター
            bukken_name: searchParams.bukken_name || '',
            bukken_state: searchParams.bukken_state || '',
            bukken_city: searchParams.bukken_city || '',
            
            // ページネーション
            query: searchParams.query || '',
            after: searchParams.after || '',
            
            // ソート
            sorts: searchParams.sorts || [
                {
                    "propertyName": "createdate",
                    "direction": "DESCENDING"
                }
            ],
            
            // 取得するプロパティ
            properties: searchParams.properties || [
                "bukken_name",
                "bukken_state", 
                "bukken_city",
                "bukken_address"
            ],
            
            // その他のオプション
            limit: searchParams.limit || 10
        }, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`, // 認証が必要な場合
                'X-API-Key': API_KEY // またはAPIキー方式
            },
            timeout: 30000 // 30秒タイムアウト
        });

        console.log('検索結果:');
        console.log('件数:', response.data.count);
        console.log('物件一覧:');
        
        response.data.results.forEach((bukken, index) => {
            console.log(`\n--- 物件 ${index + 1} ---`);
            console.log('物件名:', bukken.properties.bukken_name);
            console.log('都道府県:', bukken.properties.bukken_state);
            console.log('市区町村:', bukken.properties.bukken_city);
            console.log('住所:', bukken.properties.bukken_address);
            console.log('ID:', bukken.id);
        });

        return response.data;

    } catch (error) {
        console.error('物件検索エラー:', error.message);
        
        if (error.response) {
            console.error('ステータス:', error.response.status);
            console.error('エラー詳細:', error.response.data);
        } else if (error.request) {
            console.error('リクエストエラー:', error.request);
        } else {
            console.error('エラー:', error.message);
        }
        
        throw error;
    }
}

// 物件詳細取得のサンプル関数
async function getBukkenDetail(bukkenId) {
    try {
        console.log(`物件詳細を取得します... ID: ${bukkenId}`);

        const response = await axios.get(`${API_BASE_URL}/hubspot/bukken/${bukkenId}`, {
            headers: {
                'Authorization': `Bearer ${API_KEY}`,
                'X-API-Key': API_KEY
            },
            timeout: 30000
        });

        console.log('物件詳細:');
        console.log('ID:', response.data.id);
        console.log('プロパティ:', response.data.properties);

        return response.data;

    } catch (error) {
        console.error('物件詳細取得エラー:', error.message);
        throw error;
    }
}

// 物件作成のサンプル関数
async function createBukken(bukkenData) {
    try {
        console.log('物件を作成します...');
        console.log('物件データ:', bukkenData);

        const response = await axios.post(`${API_BASE_URL}/hubspot/bukken`, bukkenData, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`,
                'X-API-Key': API_KEY
            },
            timeout: 30000
        });

        console.log('物件作成完了:');
        console.log('ID:', response.data.id);
        console.log('作成日時:', response.data.createdAt);

        return response.data;

    } catch (error) {
        console.error('物件作成エラー:', error.message);
        throw error;
    }
}

// 物件更新のサンプル関数
async function updateBukken(bukkenId, updateData) {
    try {
        console.log(`物件を更新します... ID: ${bukkenId}`);
        console.log('更新データ:', updateData);

        const response = await axios.patch(`${API_BASE_URL}/hubspot/bukken/${bukkenId}`, updateData, {
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${API_KEY}`,
                'X-API-Key': API_KEY
            },
            timeout: 30000
        });

        console.log('物件更新完了:');
        console.log('ID:', response.data.id);
        console.log('更新日時:', response.data.updatedAt);

        return response.data;

    } catch (error) {
        console.error('物件更新エラー:', error.message);
        throw error;
    }
}

// 物件削除のサンプル関数
async function deleteBukken(bukkenId) {
    try {
        console.log(`物件を削除します... ID: ${bukkenId}`);

        const response = await axios.delete(`${API_BASE_URL}/hubspot/bukken/${bukkenId}`, {
            headers: {
                'Authorization': `Bearer ${API_KEY}`,
                'X-API-Key': API_KEY
            },
            timeout: 30000
        });

        console.log('物件削除完了');

        return response.data;

    } catch (error) {
        console.error('物件削除エラー:', error.message);
        throw error;
    }
}

// 使用例
async function main() {
    try {
        // 1. 物件検索の例
        console.log('=== 物件検索の例 ===');
        
        // 条件なしで検索
        const allResults = await searchBukken();
        
        // 物件名で検索
        const nameResults = await searchBukken({
            bukken_name: 'マンション'
        });
        
        // 都道府県で検索
        const stateResults = await searchBukken({
            bukken_state: '東京都'
        });
        
        // 市区町村で検索
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

        // 2. 物件詳細取得の例
        if (allResults.results.length > 0) {
            console.log('\n=== 物件詳細取得の例 ===');
            const firstBukken = allResults.results[0];
            await getBukkenDetail(firstBukken.id);
        }

        // 3. 物件作成の例
        console.log('\n=== 物件作成の例 ===');
        const newBukken = await createBukken({
            bukken_name: 'テスト物件',
            bukken_state: '東京都',
            bukken_city: '渋谷区',
            bukken_address: '渋谷区渋谷1-1-1'
        });

        // 4. 物件更新の例
        console.log('\n=== 物件更新の例 ===');
        await updateBukken(newBukken.id, {
            bukken_name: '更新されたテスト物件',
            bukken_address: '渋谷区渋谷1-1-2'
        });

        // 5. 物件削除の例
        console.log('\n=== 物件削除の例 ===');
        await deleteBukken(newBukken.id);

    } catch (error) {
        console.error('メイン処理エラー:', error.message);
    }
}

// エクスポート
module.exports = {
    searchBukken,
    getBukkenDetail,
    createBukken,
    updateBukken,
    deleteBukken
};

// 直接実行の場合
if (require.main === module) {
    main();
}

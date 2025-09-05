// axios を使った Mirai API 物件検索のシンプルサンプル
// 必要なパッケージ: npm install axios

const axios = require('axios');

// API設定
const API_BASE_URL = 'https://api.miraiarc.co.jp';
const API_KEY = 'your-mirai-api-key-here'; // 実際のAPIキーに変更

// 物件検索のシンプルな例
async function searchBukken() {
    try {
        console.log('物件検索を開始します...');

        const response = await axios.post(`${API_BASE_URL}/hubspot/bukken/search`, {
            // 検索条件
            bukken_name: 'マンション',        // 物件名（部分一致）
            bukken_state: '東京都',           // 都道府県（完全一致）
            bukken_city: '渋谷区',            // 市区町村（完全一致）
            
            // 取得件数
            limit: 5
        }, {
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            }
        });

        console.log('検索結果:');
        console.log('件数:', response.data.count);
        
        // 結果を表示
        response.data.results.forEach((bukken, index) => {
            console.log(`\n物件 ${index + 1}:`);
            console.log('  物件名:', bukken.properties.bukken_name);
            console.log('  都道府県:', bukken.properties.bukken_state);
            console.log('  市区町村:', bukken.properties.bukken_city);
            console.log('  住所:', bukken.properties.bukken_address);
        });

        return response.data;

    } catch (error) {
        console.error('エラーが発生しました:', error.message);
        if (error.response) {
            console.error('ステータス:', error.response.status);
            console.error('エラー詳細:', error.response.data);
        }
        throw error;
    }
}

// 物件詳細取得のシンプルな例
async function getBukkenDetail(bukkenId) {
    try {
        console.log(`物件詳細を取得します... ID: ${bukkenId}`);

        const response = await axios.get(`${API_BASE_URL}/hubspot/bukken/${bukkenId}`, {
            headers: {
                'X-API-Key': API_KEY
            }
        });

        console.log('物件詳細:');
        console.log('ID:', response.data.id);
        console.log('プロパティ:', response.data.properties);

        return response.data;

    } catch (error) {
        console.error('エラーが発生しました:', error.message);
        throw error;
    }
}

// 物件作成のシンプルな例
async function createBukken() {
    try {
        console.log('物件を作成します...');

        const response = await axios.post(`${API_BASE_URL}/hubspot/bukken`, {
            bukken_name: 'テスト物件',
            bukken_state: '東京都',
            bukken_city: '渋谷区',
            bukken_address: '渋谷区渋谷1-1-1'
        }, {
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            }
        });

        console.log('物件作成完了:');
        console.log('ID:', response.data.id);
        console.log('作成日時:', response.data.createdAt);

        return response.data;

    } catch (error) {
        console.error('エラーが発生しました:', error.message);
        throw error;
    }
}

// メイン実行関数
async function main() {
    try {
        // 1. 物件検索
        console.log('=== 物件検索 ===');
        const searchResults = await searchBukken();

        // 2. 物件詳細取得（検索結果がある場合）
        if (searchResults.results.length > 0) {
            console.log('\n=== 物件詳細取得 ===');
            const firstBukken = searchResults.results[0];
            await getBukkenDetail(firstBukken.id);
        }

        // 3. 物件作成
        console.log('\n=== 物件作成 ===');
        const newBukken = await createBukken();

        // 4. 作成した物件の詳細取得
        console.log('\n=== 作成した物件の詳細 ===');
        await getBukkenDetail(newBukken.id);

    } catch (error) {
        console.error('メイン処理でエラーが発生しました:', error.message);
    }
}

// 実行
main();

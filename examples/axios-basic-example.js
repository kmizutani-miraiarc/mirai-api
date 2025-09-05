// axios を使った Mirai API 物件検索の基本的なサンプル
// 必要なパッケージ: npm install axios

const axios = require('axios');

// 設定
const API_URL = 'https://api.miraiarc.co.jp/hubspot/bukken/search';
const API_KEY = 'your-mirai-api-key-here'; // 実際のAPIキーに変更

// 物件検索の基本的な例
async function searchBukken() {
    try {
        const response = await axios.post(API_URL, {
            bukken_name: 'マンション',
            bukken_state: '東京都',
            bukken_city: '渋谷区',
            limit: 5
        }, {
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            }
        });

        console.log('検索結果:');
        console.log('件数:', response.data.count);
        
        response.data.results.forEach((bukken, index) => {
            console.log(`${index + 1}. ${bukken.properties.bukken_name}`);
            console.log(`   ${bukken.properties.bukken_state} ${bukken.properties.bukken_city}`);
            console.log(`   ${bukken.properties.bukken_address}`);
        });

    } catch (error) {
        console.error('エラー:', error.message);
    }
}

// 実行
searchBukken();

"""
AI処理モジュール
Geminiを使用してテキストをJSONに変換する処理を担当
"""

import os
import json
import logging
import re
from typing import Dict, Any, Optional, List

import google.generativeai as genai

logger = logging.getLogger(__name__)

class AIProcessor:
    """AI処理クラス"""
    
    # Gemini API関連定数
    AVAILABLE_MODELS = [
        'gemini-1.5-flash',
        'gemini-2.0-flash', 
        'gemini-1.5-pro',
        'gemini-2.5-flash',
        'gemini-2.5-pro'
    ]
    DEFAULT_MODEL = 'gemini-1.5-flash'
    MAX_TOKENS = 4096
    TEMPERATURE = 0.1
    
    def __init__(self):
        """AIProcessorの初期化"""
        self.api_key = os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError('GEMINI_API_KEY環境変数が設定されていません')
        
        # Gemini APIの設定
        genai.configure(api_key=self.api_key)
        logger.info("AIProcessor initialized with Gemini API")
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        テキストを解析して物件情報のJSONを返す
        
        Args:
            text: 解析対象のテキスト
            
        Returns:
            解析結果の辞書
        """
        logger.info("Starting text analysis with Gemini")
        
        try:
            # 入力テキストの確認
            if not text or not text.strip():
                raise ValueError('解析対象のテキストが空です')
            
            # 利用可能なモデルを順番に試行
            for model_name in self.AVAILABLE_MODELS:
                try:
                    logger.info(f"Trying model: {model_name}")
                    result = self._analyze_with_model(text, model_name)
                    if result:
                        logger.info(f"Successfully analyzed with model: {model_name}")
                        return result
                        
                except Exception as model_error:
                    logger.warning(f"Model {model_name} failed: {str(model_error)}")
                    continue
            
            raise Exception('すべてのモデルでの解析に失敗しました')
            
        except Exception as e:
            logger.error(f"Text analysis failed: {str(e)}")
            raise
    
    def _analyze_with_model(self, text: str, model_name: str) -> Optional[Dict[str, Any]]:
        """
        指定されたモデルでテキストを解析
        
        Args:
            text: 解析対象のテキスト
            model_name: 使用するモデル名
            
        Returns:
            解析結果の辞書、失敗時はNone
        """
        try:
            # モデルの初期化
            model = genai.GenerativeModel(model_name)
            
            # プロンプトの生成
            prompt = self._create_prompt(text)
            
            # 生成設定
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
            )
            
            # コンテンツ生成
            response = model.generate_content(
                prompt,
                generation_config=generation_config
            )
            
            # レスポンスの処理
            response_text = response.text
            
            # JSONの抽出
            json_data = self._extract_json_from_response(response_text)
            
            if json_data:
                # 数値の正規化処理を適用
                json_data = self._normalize_numeric_values(json_data)
                return json_data
            else:
                logger.warning(f"Model {model_name} response did not contain valid JSON: {response_text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Model {model_name} analysis failed: {str(e)}")
            raise
    
    def _normalize_numeric_values(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        数値の正規化処理
        小数点が正しく認識されるように調整
        """
        try:
            # 数値フィールドのリスト
            numeric_fields = [
                'area', 'landArea', 'buildingArea', 'floorArea', 
                'price', 'rent', 'deposit', 'keyMoney',
                'floor', 'units', 'age', 'completionYear'
            ]
            
            for field in numeric_fields:
                if field in data and data[field] is not None:
                    value = str(data[field])
                    
                    # 数値文字列の場合のみ処理
                    if value.replace('.', '').replace(',', '').replace('-', '').isdigit():
                        # カンマを除去
                        value = value.replace(',', '')
                        
                        # 小数点の処理
                        if '.' in value:
                            # 小数点が含まれている場合はそのまま保持
                            try:
                                data[field] = float(value)
                            except ValueError:
                                # 変換に失敗した場合は元の値を保持
                                pass
                        else:
                            # 整数の場合は整数として保持
                            try:
                                data[field] = int(value)
                            except ValueError:
                                # 変換に失敗した場合は元の値を保持
                                pass
            
            return data
            
        except Exception as e:
            logger.warning(f"Number normalization failed: {str(e)}")
            return data
    
    def _create_prompt(self, text: str) -> str:
        """
        解析用のプロンプトを生成
        
        Args:
            text: 解析対象のテキスト
            
        Returns:
            生成されたプロンプト
        """
        prompt = f"""
あなたは不動産物件情報の専門解析AIです。以下の物件概要書のテキストを詳細に解析して、JSON形式で物件情報を抽出してください。

## 解析対象テキスト:
{text}

## 抽出ルール（高精度設定）:
1. **テキストの文脈を深く理解**して、該当する情報を正確に抽出してください
2. **数値の正規化**: 単位を除いた数値のみを返し、カンマ区切りは除去してください。**小数点は必ず保持**してください（例：149.88 → 149.88、14988 → 14988）
3. **住所の詳細解析**: 都道府県、市区町村、住所に正確に分割してください
4. **物件種別の判定**: 以下の候補から最も適切なものを選択し、略語も正しく解釈してください：
   - マンション（MS、マンション、分譲マンション）
   - AP（アパート、アパートメント）
   - レジ（レジデンス、レジデンシャル）
   - 戸建（戸建て、一戸建て、戸建住宅）
   - 区分MS（区分マンション、区分所有）
   - テラスハウス
   - タウンハウス
   - その他
5. **竣工年月の解析**: 和暦と西暦を正しく認識・変換し、年月形式で返してください
   - 和暦の年号（昭和、平成、令和、Ｓ、Ｈ、Ｒ等）を正しく認識してください
   - 和暦を西暦に変換してください（例：昭和50年 → 1975年、平成15年 → 2003年、令和3年 → 2021年）
   - 和暦変換表: 昭和元年=1926年、平成元年=1989年、令和元年=2019年
6. **構造の詳細解析**: 鉄筋コンクリート造、鉄骨造、木造等を正確に判定してください
7. **数値の検証**: 階数、戸数、築年数等の数値が論理的に正しいか確認してください
8. **接道情報の詳細解析**: 接道に関する情報は以下の要素を含めて全文で抽出してください
   - 方位（北、南、東、西、北東、南西等）
   - 道路幅（4m、6m、8m等）
   - 道路種別（公道、私道、市道、県道、国道等）
   - 角地情報（角地、二方路等）
   - その他特記事項（セットバック、42条2項道路等）
9. **部分的な情報も抽出**: 完全でなくても部分的に読み取れる情報は抽出してください
10. **OCRエラーの補正**: 文字の誤認識を考慮して、文脈から正しい情報を推測してください
11. **該当しない項目はnull**を返してください

## 特別な注意事項:
- テキストが不完全でも、可能な限り情報を抽出してください
- 数値の単位（㎡、坪、円等）は除去してください
- **小数点の処理**: 数値に小数点が含まれている場合は必ず保持してください（例：149.88㎡ → 149.88）
- **接道情報の全文取得**: 接道項目は数値だけでなく、方位・道路幅・道路種別を含む全文を取得してください（例：「南側4m公道」「東6m西4m私道」「北東角地8m市道」等）
- **和暦変換の詳細処理**:
  - 昭和（Ｓ、ｓ、S）: 昭和年数 + 1925 = 西暦（例：昭和50年 = 1975年）
  - 平成（Ｈ、ｈ、H）: 平成年数 + 1988 = 西暦（例：平成15年 = 2003年）
  - 令和（Ｒ、ｒ、R）: 令和年数 + 2018 = 西暦（例：令和3年 = 2021年）
  - 年月の形式は「YYYY年MM月」または「YYYY-MM」で返してください
- 住所の表記ゆれ（「1-2-3」と「1丁目2番地3号」等）を正規化してください
- 物件名の表記ゆれ（「○○マンション」と「○○マンションA棟」等）を考慮してください
   - ビル
   - 店舗
   - 店舗・共同住宅
   - その他

## 出力形式:
以下のJSON形式で返してください：

{{
  "name": "物件名（建物名や物件の正式名称）",
  "state": "都道府県（例：東京都、大阪府）",
  "city": "市区町村（例：渋谷区、中央区）",
  "address": "住所（番地以降の詳細住所）",
  "lotNumber": "地番",
  "type": "物件種別（上記候補から選択）",
  "structure": "構造（RC造、木造、S造など）",
  "floor": "階数（数値のみ）",
  "units": "戸数（数値のみ）",
  "completionYear": "竣工年月（YYYY年MM月形式）",
  "age": "築年数（数値のみ）",
  "totalFloorArea": "延床面積（数値のみ、㎡単位）",
  "landArea": "土地面積（数値のみ、㎡単位）",
  "tsubo": "坪数（数値のみ）",
  "roadPrice": "路線価（数値のみ、円/㎡単位）",
  "landAppraisal": "土地評価額（数値のみ、円単位）",
  "frontage": "接道状況（方位・道路幅・道路種別を含む全文、例：「南側4m公道」「東6m西4m私道」「北東角地8m市道」）",
  "buildingCoverageRatio": "建坪率（数値のみ、%単位）",
  "floorAreaRatio": "容積率（数値のみ、%単位）",
  "cityPlan": "都市計画（市街化区域、市街化調整区域など）",
  "useDistrict": "用途地域（第一種住居地域など）",
  "firePreventionArea": "防火地域（防火地域、準防火地域など）",
  "zoning2": "用途地域2（複数ある場合）",
  "buildingCoverageRatio2": "建坪率2（複数ある場合）",
  "floorAreaRatio2": "容積率2（複数ある場合）",
  "heightDistrict": "高度地区（高度地区、高度利用地区など）",
  "fireDistrict": "防火地域（防火地域、準防火地域など）",
  "water": "上水道（有、無、計画中など）",
  "sewerage": "下水道（有、無、計画中など）",
  "gas": "ガス（都市ガス、プロパンガス、無など）",
  "electricity": "電気（有、無など）",
  "parking": "駐車場（台数や有無）",
  "yield": "利回り（数値のみ、%単位）",
  "landPrice": "土地価格（数値のみ、円単位）",
  "buildingPrice": "建物価格（数値のみ、円単位）",
  "introductionPrice": "紹介価格（数値のみ、円単位）",
  "currentRent": "現在賃料（数値のみ、円単位）",
  "currentYield": "現在利回り（数値のみ、%単位）",
  "fullOccupancy": "満室率（数値のみ、%単位）",
  "fullOccupancyYield": "満室利回り（数値のみ、%単位）",
  "otherRestrictions": "その他制限（建築制限、用途制限など）",
  "remarks": "備考（その他の重要な情報）"
}}

## 重要な注意事項:
- 数値は必ず単位を除いて数値のみを返してください
- 土地面積は㎡単位で統一してください
- 価格は円単位で統一してください
- パーセンテージは%記号を除いて数値のみを返してください
- テキストに明記されていない情報は推測せず、nullを返してください
- 複数の値がある場合は、最も主要なものを選択してください

JSONのみを返してください。説明文やコメントは含めないでください。
"""
        return prompt
    
    def _extract_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """
        レスポンステキストからJSONを抽出
        
        Args:
            response_text: レスポンステキスト
            
        Returns:
            抽出されたJSON辞書、失敗時はNone
        """
        try:
            # 複数のJSONパターンを試行
            json_patterns = [
                r'\{[\s\S]*\}',  # 基本的なJSONパターン
                r'```json\s*(\{[\s\S]*?\})\s*```',  # Markdownコードブロック
                r'```\s*(\{[\s\S]*?\})\s*```',  # コードブロック
                r'JSON:\s*(\{[\s\S]*?\})',  # JSON: プレフィックス
                r'Response:\s*(\{[\s\S]*?\})',  # Response: プレフィックス
            ]
            
            for pattern in json_patterns:
                json_match = re.search(pattern, response_text, re.IGNORECASE)
                if json_match:
                    json_str = json_match.group(1) if len(json_match.groups()) > 0 else json_match.group(0)
                    
                    try:
                        # JSONをパース
                        json_data = json.loads(json_str)
                        
                        # データの検証とクリーニング
                        cleaned_data = self._clean_analysis_result(json_data)
                        
                        logger.info(f"Successfully extracted JSON using pattern: {pattern}")
                        return cleaned_data
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"JSON parsing failed for pattern {pattern}: {str(e)}")
                        continue
            
            # パターンマッチが失敗した場合は、テキスト全体をJSONとして試行
            logger.warning("No JSON pattern matched, trying to parse entire response as JSON")
            try:
                json_data = json.loads(response_text.strip())
                cleaned_data = self._clean_analysis_result(json_data)
                return cleaned_data
            except json.JSONDecodeError:
                pass
            
            logger.warning("No valid JSON found in response")
            return None
                
        except Exception as e:
            logger.error(f"JSON extraction failed: {str(e)}")
            return None
    
    def _clean_analysis_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        解析結果をクリーニング
        
        Args:
            data: 解析結果の辞書
            
        Returns:
            クリーニングされた辞書
        """
        cleaned_data = {}
        
        # 期待されるフィールドのリスト
        expected_fields = [
            "name", "state", "city", "address", "lotNumber", "type", "structure",
            "floor", "units", "completionYear", "age", "totalFloorArea", "landArea", 
            "tsubo", "roadPrice", "landAppraisal", "frontage", "buildingCoverageRatio", 
            "floorAreaRatio", "cityPlan", "useDistrict", "firePreventionArea", 
            "zoning2", "buildingCoverageRatio2", "floorAreaRatio2", "heightDistrict", 
            "fireDistrict", "water", "sewerage", "gas", "electricity", "parking", 
            "yield", "landPrice", "buildingPrice", "introductionPrice", "currentRent", 
            "currentYield", "fullOccupancy", "fullOccupancyYield", "otherRestrictions", 
            "remarks"
        ]
        
        # 数値フィールドのリスト
        numeric_fields = [
            "floor", "units", "age", "totalFloorArea", "landArea", "tsubo", 
            "roadPrice", "landAppraisal", "frontage", "buildingCoverageRatio", 
            "floorAreaRatio", "buildingCoverageRatio2", "floorAreaRatio2", 
            "yield", "landPrice", "buildingPrice", "introductionPrice", 
            "currentRent", "currentYield", "fullOccupancy", "fullOccupancyYield"
        ]
        
        for field in expected_fields:
            value = data.get(field)
            
            # 値のクリーニング
            if value is None or value == "":
                cleaned_data[field] = None
            elif isinstance(value, str):
                # 文字列のトリム
                cleaned_value = value.strip()
                if cleaned_value == "":
                    cleaned_data[field] = None
                else:
                    # 数値フィールドの場合は数値変換を試行
                    if field in numeric_fields:
                        cleaned_data[field] = self._clean_numeric_value(cleaned_value)
                    else:
                        cleaned_data[field] = cleaned_value
            else:
                cleaned_data[field] = value
        
        return cleaned_data
    
    def _clean_numeric_value(self, value: str) -> Optional[float]:
        """
        数値文字列をクリーニングして数値に変換
        
        Args:
            value: 数値文字列
            
        Returns:
            変換された数値、失敗時はNone
        """
        try:
            # 不要な文字を除去
            cleaned = re.sub(r'[^\d.,\-]', '', value)
            
            # カンマを除去
            cleaned = cleaned.replace(',', '')
            
            # 空文字列の場合はNone
            if not cleaned:
                return None
            
            # 数値に変換
            return float(cleaned)
            
        except (ValueError, TypeError):
            logger.warning(f"Failed to convert numeric value: {value}")
            return None
    
    def validate_analysis_result(self, data: Dict[str, Any]) -> bool:
        """
        解析結果の妥当性を検証
        
        Args:
            data: 解析結果の辞書
            
        Returns:
            妥当性の真偽値
        """
        try:
            # 必須フィールドのチェック
            required_fields = ["name"]
            for field in required_fields:
                if not data.get(field):
                    logger.warning(f"Required field '{field}' is missing or empty")
                    return False
            
            # 数値フィールドのチェック
            numeric_fields = ["floor", "units", "age", "totalFloorArea", "landArea", 
                            "tsubo", "roadPrice", "landAppraisal", "buildingCoverageRatio", 
                            "floorAreaRatio"]
            
            for field in numeric_fields:
                value = data.get(field)
                if value is not None and value != "":
                    try:
                        # 数値に変換可能かチェック
                        float(str(value).replace(',', ''))
                    except (ValueError, TypeError):
                        logger.warning(f"Field '{field}' contains invalid numeric value: {value}")
                        # 数値でない場合はNoneに設定
                        data[field] = None
            
            return True
            
        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            return False

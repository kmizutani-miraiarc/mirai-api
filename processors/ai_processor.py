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
                return json_data
            else:
                logger.warning(f"Model {model_name} response did not contain valid JSON: {response_text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Model {model_name} analysis failed: {str(e)}")
            raise
    
    def _create_prompt(self, text: str) -> str:
        """
        解析用のプロンプトを生成
        
        Args:
            text: 解析対象のテキスト
            
        Returns:
            生成されたプロンプト
        """
        prompt = f"""
以下の物件概要書のテキストを解析して、JSON形式で物件情報を抽出してください。

テキスト:
{text}

以下の形式でJSONを返してください（該当しない項目はnullまたは空文字列）:
{{
  "name": "物件名",
  "state": "都道府県",
  "city": "市区町村",
  "address": "住所",
  "lotNumber": "地番",
  "type": "物件種別",
  "structure": "構造",
  "floor": "階数",
  "units": "戸数",
  "completionYear": "竣工年月",
  "age": "築年",
  "totalFloorArea": "延床面積",
  "landArea": "土地面積（㎡単位、数値のみ）",
  "tsubo": "坪数",
  "roadPrice": "路線価",
  "landAppraisal": "土地評価額",
  "frontage": "間口",
  "buildingCoverageRatio": "建坪率",
  "floorAreaRatio": "容積率",
  "cityPlan": "都市計画",
  "useDistrict": "用途地域",
  "firePreventionArea": "防火地域",
  "zoning2": "用途地域2",
  "buildingCoverageRatio2": "建坪率2",
  "floorAreaRatio2": "容積率2",
  "heightDistrict": "高度地区",
  "fireDistrict": "防火地域",
  "water": "上水道",
  "sewerage": "下水道",
  "gas": "ガス",
  "electricity": "電気",
  "parking": "駐車場",
  "yield": "利回り",
  "landPrice": "土地価格",
  "buildingPrice": "建物価格",
  "introductionPrice": "紹介価格",
  "currentRent": "現在賃料",
  "currentYield": "現在利回り",
  "fullOccupancy": "満室率",
  "fullOccupancyYield": "満室利回り",
  "otherRestrictions": "その他制限",
  "remarks": "備考"
}}

特に注意点：
- 土地面積（landArea）は㎡単位の数値のみを抽出してください
- 物件種別は「マンション」「AP」「レジ」「戸建」「区分MS」「ビル」「店舗」「店舗・共同住宅」「その他」などから適切なものを選択してください
- 数値項目は単位を除いた数値のみを返してください

JSONのみを返してください。説明文は含めないでください。
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
            # JSONパターンを検索
            json_pattern = r'\{[\s\S]*\}'
            json_match = re.search(json_pattern, response_text)
            
            if json_match:
                json_str = json_match.group(0)
                # JSONをパース
                json_data = json.loads(json_str)
                
                # データの検証とクリーニング
                cleaned_data = self._clean_analysis_result(json_data)
                
                return cleaned_data
            else:
                logger.warning("No JSON pattern found in response")
                return None
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
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
                    cleaned_data[field] = cleaned_value
            else:
                cleaned_data[field] = value
        
        return cleaned_data
    
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

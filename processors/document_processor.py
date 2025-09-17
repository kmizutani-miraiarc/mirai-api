"""
文書処理モジュール
PDFや画像からテキストを抽出する処理を担当
Google Vision APIとローカルOCRの両方に対応
"""

import os
import tempfile
import logging
import json
from typing import Optional, Dict, Any
from pathlib import Path

from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import PyPDF2

# ロガーの初期化
logger = logging.getLogger(__name__)

# Google Vision API関連のインポート
try:
    from google.cloud import vision
    from google.api_core import exceptions as gcp_exceptions
    VISION_API_AVAILABLE = True
except ImportError:
    VISION_API_AVAILABLE = False
    logger.warning("Google Vision API not available. Install google-cloud-vision to enable Vision API OCR.")

class DocumentProcessor:
    """文書処理クラス"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        
        # Google Vision APIの初期化
        self.vision_client = None
        self.vision_api_enabled = False
        self.vision_api_quota_exceeded = False
        
        if VISION_API_AVAILABLE:
            try:
                # 環境変数から認証情報を取得
                credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
                if credentials_path and os.path.exists(credentials_path):
                    self.vision_client = vision.ImageAnnotatorClient()
                    self.vision_api_enabled = True
                    logger.info("Google Vision API initialized successfully")
                else:
                    logger.warning("GOOGLE_APPLICATION_CREDENTIALS not set or file not found. Vision API disabled.")
            except Exception as e:
                logger.warning(f"Failed to initialize Google Vision API: {str(e)}")
        
        logger.info(f"DocumentProcessor initialized with temp dir: {self.temp_dir}")
        logger.info(f"Vision API enabled: {self.vision_api_enabled}")
    
    def process_file(self, file_path: str, file_type: str) -> str:
        """
        ファイルを処理してテキストを抽出
        
        Args:
            file_path: ファイルのパス
            file_type: ファイルの種類 ('pdf' または 'image')
            
        Returns:
            抽出されたテキスト
        """
        try:
            if file_type.lower() == 'pdf':
                return self._extract_text_from_pdf(file_path)
            elif file_type.lower() in ['image', 'jpg', 'jpeg', 'png', 'bmp', 'tiff']:
                return self._extract_text_from_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        PDFからテキストを抽出
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        try:
            # まずPyPDF2でテキスト抽出を試行
            text = self._extract_text_from_pdf_with_pypdf2(pdf_path)
            
            # テキストが少ない場合はOCRを使用
            if len(text.strip()) < 50:
                logger.info("PyPDF2 extraction yielded little text, trying OCR")
                text = self._extract_text_from_pdf_with_ocr(pdf_path)
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {str(e)}")
            raise
    
    def _extract_text_from_pdf_with_pypdf2(self, pdf_path: str) -> str:
        """PyPDF2を使用してPDFからテキストを抽出"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
        except Exception as e:
            logger.warning(f"PyPDF2 extraction failed: {str(e)}")
        return text
    
    def _extract_text_from_pdf_with_ocr(self, pdf_path: str) -> str:
        """OCRを使用してPDFからテキストを抽出（高精度設定）"""
        try:
            # 最適化されたDPIで試行（パフォーマンス重視）
            dpi_options = [400]  # 400DPIのみで高速処理
            best_text = ""
            best_confidence = 0
            
            for dpi in dpi_options:
                try:
                    logger.info(f"Trying OCR with DPI: {dpi}")
                    # PDFを画像に変換（パフォーマンス最適化）
                    images = convert_from_path(pdf_path, dpi=dpi, first_page=1, last_page=3)  # 最初の3ページのみ処理
                    
                    page_texts = []
                    total_confidence = 0
                    valid_pages = 0
                    
                    for i, image in enumerate(images):
                        # 一時ファイルとして保存
                        temp_image_path = os.path.join(self.temp_dir, f"page_{i}_dpi_{dpi}.png")
                        image.save(temp_image_path, 'PNG')
                        
                        # 画像の前処理
                        processed_image = self._preprocess_image(image)
                        
                        # OCRでテキスト抽出
                        page_text = self._extract_text_with_multiple_configs(processed_image)
                        
                        if page_text.strip():
                            page_texts.append(page_text)
                            valid_pages += 1
                    
                    # 全ページのテキストを結合
                    combined_text = "\n".join(page_texts)
                    
                    # テキストの品質を評価（長さと文字の多様性）
                    text_quality = self._evaluate_text_quality(combined_text)
                    
                    logger.info(f"DPI {dpi}: text_length={len(combined_text)}, quality_score={text_quality:.2f}")
                    
                    if text_quality > best_confidence:
                        best_confidence = text_quality
                        best_text = combined_text
                        
                except Exception as e:
                    logger.warning(f"OCR with DPI {dpi} failed: {str(e)}")
                    continue
            
            logger.info(f"Best OCR result: quality_score={best_confidence:.2f}, text_length={len(best_text)}")
            return best_text
            
        except Exception as e:
            logger.error(f"PDF OCR extraction failed: {str(e)}")
            return ""
    
    def _evaluate_text_quality(self, text: str) -> float:
        """テキストの品質を評価（0-1のスコア）"""
        if not text.strip():
            return 0.0
        
        # 基本的な品質指標
        length_score = min(len(text) / 1000, 1.0)  # 長さスコア（最大1.0）
        
        # 文字の多様性（日本語文字の割合）
        japanese_chars = len([c for c in text if '\u3040' <= c <= '\u309F' or '\u30A0' <= c <= '\u30FF' or '\u4E00' <= c <= '\u9FAF'])
        diversity_score = min(japanese_chars / len(text), 1.0) if text else 0.0
        
        # 数値の存在（物件情報に重要）
        numbers = len([c for c in text if c.isdigit()])
        number_score = min(numbers / 100, 1.0) if text else 0.0
        
        # 総合スコア
        total_score = (length_score * 0.4 + diversity_score * 0.4 + number_score * 0.2)
        return total_score
    
    def _extract_text_from_image(self, image_path: str) -> str:
        """
        画像からテキストを抽出
        Google Vision APIを優先し、失敗時はローカルOCRにフォールバック
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        try:
            # Google Vision APIが有効で、クォータが残っている場合はVision APIを使用
            if self.vision_api_enabled and not self.vision_api_quota_exceeded:
                try:
                    text = self._extract_text_with_vision_api(image_path)
                    if text:
                        logger.info("Successfully extracted text using Google Vision API")
                        return text
                except Exception as e:
                    logger.warning(f"Vision API extraction failed: {str(e)}")
                    # クォータエラーの場合はフラグを設定
                    if "quota" in str(e).lower() or "limit" in str(e).lower():
                        self.vision_api_quota_exceeded = True
                        logger.warning("Vision API quota exceeded, switching to local OCR")
            
            # ローカルOCRでテキスト抽出
            logger.info("Using local OCR for text extraction")
            return self._extract_text_with_local_ocr(image_path)
            
        except Exception as e:
            logger.error(f"Error extracting text from image {image_path}: {str(e)}")
            raise
    
    def _extract_text_with_vision_api(self, image_path: str) -> str:
        """
        Google Vision APIを使用してテキストを抽出
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        try:
            # 画像ファイルを読み込み
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            # Vision APIでテキスト検出
            image = vision.Image(content=content)
            response = self.vision_client.text_detection(image=image)
            
            # エラーチェック
            if response.error.message:
                raise Exception(f"Vision API error: {response.error.message}")
            
            # テキストを抽出
            texts = response.text_annotations
            if texts:
                # 最初の要素は全体のテキスト
                return texts[0].description
            else:
                return ""
                
        except gcp_exceptions.ResourceExhausted:
            logger.warning("Vision API quota exceeded")
            self.vision_api_quota_exceeded = True
            raise Exception("Vision API quota exceeded")
        except Exception as e:
            logger.error(f"Vision API extraction failed: {str(e)}")
            raise
    
    def _extract_text_with_local_ocr(self, image_path: str) -> str:
        """
        ローカルOCR（Tesseract）を使用してテキストを抽出
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        try:
            # 画像を開く
            image = Image.open(image_path)
            
            # 画像の前処理
            processed_image = self._preprocess_image(image)
            
            # 複数のOCR設定を試行して最適な結果を選択
            text = self._extract_text_with_multiple_configs(processed_image)
            
            return text
        except Exception as e:
            logger.error(f"Local OCR extraction failed: {str(e)}")
            raise
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """画像の前処理でOCR精度を向上"""
        try:
            # グレースケール変換
            if image.mode != 'L':
                image = image.convert('L')
            
            # 画像のサイズを調整（パフォーマンス最適化）
            width, height = image.size
            if width < 800 or height < 800:  # 閾値を下げて処理を高速化
                # 小さな画像は拡大
                scale_factor = max(800 / width, 800 / height)
                new_width = int(width * scale_factor)
                new_height = int(height * scale_factor)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # コントラストと明度の調整
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(1.5)  # コントラストを1.5倍に
            
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)  # シャープネスを2倍に
            
            return image
            
        except Exception as e:
            logger.warning(f"Image preprocessing failed: {str(e)}")
            return image
    
    def _extract_text_with_multiple_configs(self, image: Image.Image) -> str:
        """複数のOCR設定を試行して最適な結果を選択"""
        try:
            # OCR設定のリスト（パフォーマンス重視）
            ocr_configs = [
                # 高精度設定（日本語+英語）- 最適化
                {
                    'config': r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽゃゅょっー・、。！？（）「」【】',
                    'lang': 'jpn+eng'
                },
                # 自動ページ分割（フォールバック）
                {
                    'config': r'--oem 3 --psm 3',
                    'lang': 'jpn+eng'
                }
            ]
            
            best_text = ""
            best_confidence = 0
            
            for i, config in enumerate(ocr_configs):
                try:
                    # テキスト抽出
                    text = pytesseract.image_to_string(image, config=config['config'], lang=config['lang'])
                    
                    # 信頼度を取得
                    data = pytesseract.image_to_data(
                        image, 
                        config=config['config'], 
                        lang=config['lang'], 
                        output_type=pytesseract.Output.DICT
                    )
                    
                    confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
                    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
                    
                    logger.info(f"OCR config {i+1}: confidence={avg_confidence:.2f}%, text_length={len(text.strip())}")
                    
                    if avg_confidence > best_confidence and len(text.strip()) > len(best_text.strip()):
                        best_confidence = avg_confidence
                        best_text = text.strip()
                        
                        # 早期終了条件: 十分な品質の結果が得られたら処理を終了
                        if avg_confidence > 80.0 and len(text.strip()) > 200:
                            logger.info(f"Early termination: confidence={avg_confidence:.2f}% > 80%, text_length={len(text.strip())} > 200")
                            break
                        
                except Exception as e:
                    logger.warning(f"OCR config {i+1} failed: {str(e)}")
                    continue
            
            logger.info(f"Best OCR result: confidence={best_confidence:.2f}%, text_length={len(best_text)}")
            return best_text
            
        except Exception as e:
            logger.error(f"Multiple OCR configs failed: {str(e)}")
            # フォールバック: 基本的な設定で試行
            try:
                return pytesseract.image_to_string(image, lang='jpn+eng')
            except:
                return ""
    
    def get_ocr_status(self) -> Dict[str, Any]:
        """
        OCR処理の現在の状態を取得
        
        Returns:
            状態情報の辞書
        """
        return {
            "vision_api_available": VISION_API_AVAILABLE,
            "vision_api_enabled": self.vision_api_enabled,
            "vision_api_quota_exceeded": self.vision_api_quota_exceeded,
            "current_ocr_method": "vision_api" if (self.vision_api_enabled and not self.vision_api_quota_exceeded) else "local_ocr"
        }
    
    def reset_vision_api_quota(self):
        """Vision APIのクォータフラグをリセット（テスト用）"""
        self.vision_api_quota_exceeded = False
        logger.info("Vision API quota flag reset")
    
    def cleanup(self):
        """一時ファイルをクリーンアップ"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")
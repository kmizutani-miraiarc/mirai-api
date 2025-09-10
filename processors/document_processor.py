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

# Google Vision API関連のインポート
try:
    from google.cloud import vision
    from google.api_core import exceptions as gcp_exceptions
    VISION_API_AVAILABLE = True
except ImportError:
    VISION_API_AVAILABLE = False
    logger.warning("Google Vision API not available. Install google-cloud-vision to enable Vision API OCR.")

logger = logging.getLogger(__name__)

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
        """OCRを使用してPDFからテキストを抽出"""
        try:
            # PDFを画像に変換
            images = convert_from_path(pdf_path, dpi=300)
            
            text = ""
            for i, image in enumerate(images):
                # 一時ファイルとして保存
                temp_image_path = os.path.join(self.temp_dir, f"page_{i}.png")
                image.save(temp_image_path, 'PNG')
                
                # OCRでテキスト抽出
                page_text = self._extract_text_from_image(temp_image_path)
                text += page_text + "\n"
                
                # 一時ファイルを削除
                os.remove(temp_image_path)
            
            return text
        except Exception as e:
            logger.error(f"OCR extraction from PDF failed: {str(e)}")
            raise
    
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
            
            # OCRでテキスト抽出（日本語と英語）
            text = pytesseract.image_to_string(image, lang='jpn+eng')
            
            return text
        except Exception as e:
            logger.error(f"Local OCR extraction failed: {str(e)}")
            raise
    
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
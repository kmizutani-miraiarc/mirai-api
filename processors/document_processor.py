"""
文書処理モジュール
PDFや画像からテキストを抽出する処理を担当
"""

import os
import tempfile
import logging
from typing import Optional
from pathlib import Path

from PIL import Image
import pytesseract
from pdf2image import convert_from_path
import PyPDF2

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """文書処理クラス"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"DocumentProcessor initialized with temp dir: {self.temp_dir}")
    
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
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        try:
            # 画像を開く
            image = Image.open(image_path)
            
            # OCRでテキスト抽出
            text = pytesseract.image_to_string(image, lang='jpn+eng')
            
            return text
        except Exception as e:
            logger.error(f"Error extracting text from image {image_path}: {str(e)}")
            raise
    
    def cleanup(self):
        """一時ファイルをクリーンアップ"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup temp directory: {str(e)}")
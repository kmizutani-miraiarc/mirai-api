"""
文書処理モジュール
PDFや画像からテキストを抽出する処理を担当
"""

import os
import tempfile
import logging
from typing import Optional, List, Tuple
from pathlib import Path

import cv2
import numpy as np
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
            file_type: ファイルタイプ ('pdf' または 'image')
            
        Returns:
            抽出されたテキスト
        """
        try:
            if file_type.lower() == 'pdf':
                return self._process_pdf(file_path)
            elif file_type.lower() in ['image', 'jpg', 'jpeg', 'png', 'bmp', 'tiff']:
                return self._process_image(file_path)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
                
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise
    
    def _process_pdf(self, pdf_path: str) -> str:
        """
        PDFファイルを処理してテキストを抽出
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        logger.info(f"Processing PDF: {pdf_path}")
        
        # まずPyPDF2でテキスト抽出を試行
        try:
            text = self._extract_text_from_pdf(pdf_path)
            if text and len(text.strip()) > 50:  # 十分なテキストが抽出できた場合
                logger.info("Successfully extracted text using PyPDF2")
                return text
        except Exception as e:
            logger.warning(f"PyPDF2 text extraction failed: {str(e)}")
        
        # PyPDF2で失敗した場合は画像変換してOCR
        logger.info("Converting PDF to images for OCR processing")
        return self._pdf_to_images_and_ocr(pdf_path)
    
    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """
        PyPDF2を使用してPDFからテキストを抽出
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    text += page.extract_text() + "\n"
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {str(e)}")
            raise
        
        return text.strip()
    
    def _pdf_to_images_and_ocr(self, pdf_path: str) -> str:
        """
        PDFを画像に変換してOCR処理
        
        Args:
            pdf_path: PDFファイルのパス
            
        Returns:
            OCRで抽出されたテキスト
        """
        try:
            # PDFを画像に変換
            images = convert_from_path(pdf_path, dpi=300)
            logger.info(f"Converted PDF to {len(images)} images")
            
            all_text = ""
            for i, image in enumerate(images):
                logger.info(f"Processing page {i+1}/{len(images)}")
                
                # 画像を一時ファイルに保存
                temp_image_path = os.path.join(self.temp_dir, f"page_{i+1}.png")
                image.save(temp_image_path, 'PNG')
                
                # OCR処理
                page_text = self._process_image(temp_image_path)
                all_text += f"\n--- Page {i+1} ---\n{page_text}\n"
                
                # 一時ファイルを削除
                os.remove(temp_image_path)
            
            return all_text.strip()
            
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {str(e)}")
            raise
    
    def _process_image(self, image_path: str) -> str:
        """
        画像ファイルを処理してテキストを抽出
        
        Args:
            image_path: 画像ファイルのパス
            
        Returns:
            抽出されたテキスト
        """
        logger.info(f"Processing image: {image_path}")
        
        try:
            # 画像を読み込み
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not load image: {image_path}")
            
            # 画像を前処理
            processed_image = self._preprocess_image(image)
            
            # OCR処理
            text = self._extract_text_with_ocr(processed_image)
            
            return text.strip()
            
        except Exception as e:
            logger.error(f"Image processing failed: {str(e)}")
            raise
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        画像を前処理してOCRの精度を向上
        
        Args:
            image: 入力画像
            
        Returns:
            前処理された画像
        """
        try:
            # グレースケール変換
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            
            # ノイズ除去
            denoised = cv2.medianBlur(gray, 3)
            
            # コントラスト調整
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(denoised)
            
            # 二値化
            _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # モルフォロジー演算でノイズ除去
            kernel = np.ones((1,1), np.uint8)
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            # 前処理に失敗した場合は元の画像を返す
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    def _extract_text_with_ocr(self, image: np.ndarray) -> str:
        """
        OCRを使用してテキストを抽出
        
        Args:
            image: 前処理された画像
            
        Returns:
            抽出されたテキスト
        """
        try:
            # Tesseractの設定
            config = '--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyzあいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽゃゅょっー・、。！？（）「」【】￥％＆＃＠＋－＝＜＞'
            
            # OCR実行
            text = pytesseract.image_to_string(image, lang='jpn+eng', config=config)
            
            # テキストの後処理
            cleaned_text = self._clean_extracted_text(text)
            
            return cleaned_text
            
        except Exception as e:
            logger.error(f"OCR processing failed: {str(e)}")
            raise
    
    def _clean_extracted_text(self, text: str) -> str:
        """
        抽出されたテキストをクリーニング
        
        Args:
            text: 抽出されたテキスト
            
        Returns:
            クリーニングされたテキスト
        """
        if not text:
            return ""
        
        # 改行文字の正規化
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # 連続する空白や改行を整理
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line:  # 空行でない場合のみ追加
                lines.append(line)
        
        return '\n'.join(lines)
    
    def cleanup(self):
        """一時ファイルをクリーンアップ"""
        try:
            import shutil
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
    
    def __del__(self):
        """デストラクタでクリーンアップ"""
        self.cleanup()

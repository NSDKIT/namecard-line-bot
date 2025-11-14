import os
from google.cloud import vision
import re
from typing import List, Dict, Optional
import numpy as np
from collections import defaultdict

class OCRProcessor:
    def __init__(self, credentials_path=None):
        self.client = vision.ImageAnnotatorClient()
    
    def process_image(self, image_path):
        """画像から名刺情報を抽出（複数枚対応）"""
        try:
            print(f"🔍 Processing: {image_path}")
            
            # テキストとレイアウト情報を取得
            text_blocks = self.ocr_image_with_layout(image_path)
            
            if not text_blocks:
                print("⚠️ No text detected")
                return []
            
            # 名刺ごとにグループ化
            namecard_groups = self.group_text_by_namecard(text_blocks)
            
            print(f"📇 Found {len(namecard_groups)} namecard(s)")
            
            # 各名刺から情報を抽出
            results = []
            for i, group in enumerate(namecard_groups, 1):
                text = '\n'.join([block['text'] for block in group])
                info = self.extract_info_from_text(text)
                if info:
                    print(f"✅ Card {i}: {info.get('name', 'Unknown')}, {info.get('company', 'Unknown')}")
                    results.append(info)
            
            return results if results else None
            
        except Exception as e:
            print(f"❌ Error in process_image: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def ocr_image_with_layout(self, image_path):
        """Google Cloud Vision APIでOCR実行（レイアウト情報付き）"""
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            image_context = vision.ImageContext(language_hints=['ja', 'en'])
            
            response = self.client.document_text_detection(
                image=image,
                image_context=image_context
            )
            
            if response.error.message:
                raise Exception(f'API Error: {response.error.message}')
            
            text_blocks = []
            
            # ページ情報から各ブロックを取得
            for page in response.full_text_annotation.pages:
                for block in page.blocks:
                    # ブロックの座標
                    vertices = [(v.x, v.y) for v in block.bounding_box.vertices]
                    x_coords = [v[0] for v in vertices]
                    y_coords = [v[1] for v in vertices]
                    
                    # ブロックのテキストを結合
                    block_text = ''
                    for paragraph in block.paragraphs:
                        for word in paragraph.words:
                            word_text = ''.join([symbol.text for symbol in word.symbols])
                            block_text += word_text
                        block_text += '\n'
                    
                    text_blocks.append({
                        'text': block_text.strip(),
                        'x': sum(x_coords) / len(x_coords),
                        'y': sum(y_coords) / len(y_coords),
                        'width': max(x_coords) - min(x_coords),
                        'height': max(y_coords) - min(y_coords),
                        'vertices': vertices
                    })
            
            return text_blocks
        
        except Exception as e:
            print(f"❌ OCR Error: {e}")
            raise
    
    def group_text_by_namecard(self, text_blocks, max_cards=9):
        """テキストブロックを名刺ごとにグループ化"""
        if not text_blocks:
            return []
        
        # Y座標でソート
        sorted_blocks = sorted(text_blocks, key=lambda b: b['y'])
        
        # Y座標の差が大きい場所で分割（行として）
        rows = []
        current_row = [sorted_blocks[0]]
        
        for block in sorted_blocks[1:]:
            # 前のブロックとのY座標差が大きければ新しい行
            if abs(block['y'] - current_row[-1]['y']) > 50:
                rows.append(current_row)
                current_row = [block]
            else:
                current_row.append(block)
        rows.append(current_row)
        
        # 各行内でX座標でソートして名刺を分割
        namecards = []
        
        for row in rows:
            row_sorted = sorted(row, key=lambda b: b['x'])
            
            # X座標の差が大きい場所で分割
            current_card = [row_sorted[0]]
            
            for block in row_sorted[1:]:
                # 前のブロックとのX座標差が大きければ新しい名刺
                if abs(block['x'] - current_card[-1]['x']) > 200:
                    namecards.append(current_card)
                    current_card = [block]
                else:
                    current_card.append(block)
            namecards.append(current_card)
        
        # 最大9枚まで
        return namecards[:max_cards]
    
    def extract_info_from_text(self, text):
        """テキストから名刺情報を抽出"""
        if not text or not text.strip():
            return None
        
        return {
            'name': self.extract_name(text),
            'company': self.extract_company(text),
            'email': self.extract_email(text),
            'phone': self.extract_phone(text),
            'mobile': self.extract_mobile(text),
            'address': self.extract_address(text),
            'website': self.extract_website(text),
            'full_text': text
        }
    
    def extract_email(self, text):
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        return emails[0] if emails else None
    
    def extract_phone(self, text):
        text = text.replace(' ', '').replace('　', '')
        patterns = [r'(?:TEL|Tel|tel|電話)?[:\s]*0\d{1,4}-\d{1,4}-\d{4}', r'(?:TEL|Tel|tel|電話)?[:\s]*0\d{9,10}']
        for pattern in patterns:
            phones = re.findall(pattern, text, re.IGNORECASE)
            if phones:
                phone = re.sub(r'(?:TEL|Tel|tel|電話)[:\s]*', '', phones[0], flags=re.IGNORECASE)
                if not phone.startswith(('070', '080', '090')):
                    return phone
        return None
    
    def extract_mobile(self, text):
        text = text.replace(' ', '').replace('　', '')
        mobiles = re.findall(r'(?:Mobile|mobile|携帯|FAX)?[:\s]*0[789]0-?\d{4}-?\d{4}', text, re.IGNORECASE)
        for mobile in mobiles:
            if 'FAX' not in mobile and 'fax' not in mobile:
                return re.sub(r'(?:Mobile|mobile|携帯)[:\s]*', '', mobile, flags=re.IGNORECASE)
        return None
    
    def extract_name(self, text):
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if re.match(r'^[\u4E00-\u9FFF]{2,4}[\s　]+[\u4E00-\u9FFF]{1,4}$', line):
                return line
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line):
                return line
        return None
    
    def extract_company(self, text):
        keywords = ['株式会社', '有限会社', '合同会社', 'Co.', 'Ltd.', 'Inc.', 'Corp.']
        lines = text.split('\n')
        for line in lines[:10]:
            for keyword in keywords:
                if keyword in line:
                    return line.strip()
        return None
    
    def extract_address(self, text):
        prefectures = ['東京都', '大阪府', '京都府', '北海道', '県']
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if re.search(r'〒?\d{3}-?\d{4}', line) or any(p in line for p in prefectures):
                address = line
                if i + 1 < len(lines):
                    address += ' ' + lines[i + 1]
                return address.strip()
        return None
    
    def extract_website(self, text):
        patterns = [r'https?://[^\s]+', r'www\.[^\s]+', r'[a-zA-Z0-9.-]+\.(com|co\.jp|jp|net|org)']
        for pattern in patterns:
            websites = re.findall(pattern, text, re.IGNORECASE)
            if websites:
                return websites[0].strip()
        return None

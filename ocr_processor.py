import os
from google.cloud import vision
import re

class OCRProcessor:
    def __init__(self, credentials_path=None):
        """OCRプロセッサーの初期化"""
        self.client = vision.ImageAnnotatorClient()
    
    def process_image(self, image_path):
        """画像から名刺情報を抽出"""
        try:
            print(f"🔍 Processing: {image_path}")
            text = self.ocr_image(image_path)
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
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def ocr_image(self, image_path):
        """Google Cloud Vision APIでOCR"""
        with open(image_path, 'rb') as f:
            content = f.read()
        
        image = vision.Image(content=content)
        response = self.client.text_detection(
            image=image,
            image_context=vision.ImageContext(language_hints=['ja', 'en'])
        )
        
        if response.error.message:
            raise Exception(f'API Error: {response.error.message}')
        
        return response.text_annotations[0].description if response.text_annotations else ""
    
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

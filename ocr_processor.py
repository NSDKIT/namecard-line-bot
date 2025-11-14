import os
from google.cloud import vision
import re

class OCRProcessor:
    def __init__(self, credentials_path=None):
        """
        OCRプロセッサーの初期化
        credentials_pathは無視（環境変数から読み込む）
        """
        self.client = vision.ImageAnnotatorClient()
    
    def process_image(self, image_path):
        """
        画像から名刺情報を抽出
        """
        try:
            print(f"🔍 Processing image: {image_path}")
            
            text = self.ocr_image(image_path)
            
            if not text or not text.strip():
                print("⚠️ No text detected")
                return None
            
            print(f"📝 Detected text length: {len(text)} characters")
            
            info = {
                'name': self.extract_name(text),
                'company': self.extract_company(text),
                'email': self.extract_email(text),
                'phone': self.extract_phone(text),
                'mobile': self.extract_mobile(text),
                'address': self.extract_address(text),
                'website': self.extract_website(text),
                'full_text': text
            }
            
            print(f"✅ Extracted: {info['name']}, {info['company']}")
            
            return info
        
        except Exception as e:
            print(f"❌ Error in process_image: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def ocr_image(self, image_path):
        """Google Cloud Vision APIでOCR実行"""
        try:
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            image_context = vision.ImageContext(language_hints=['ja', 'en'])
            
            response = self.client.text_detection(
                image=image,
                image_context=image_context
            )
            
            if response.error.message:
                raise Exception(f'API Error: {response.error.message}')
            
            texts = response.text_annotations
            
            if texts:
                return texts[0].description
            
            return ""
        
        except Exception as e:
            print(f"❌ OCR Error: {e}")
            raise
    
    def extract_email(self, text):
        """メールアドレスを抽出"""
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(pattern, text)
        return emails[0] if emails else None
    
    def extract_phone(self, text):
        """固定電話番号を抽出"""
        text_cleaned = text.replace(' ', '').replace('　', '')
        patterns = [
            r'(?:TEL|Tel|tel|電話)?[:\s]*0\d{1,4}-\d{1,4}-\d{4}',
            r'(?:TEL|Tel|tel|電話)?[:\s]*0\d{9,10}',
        ]
        
        for pattern in patterns:
            phones = re.findall(pattern, text_cleaned, re.IGNORECASE)
            if phones:
                phone = re.sub(r'(?:TEL|Tel|tel|電話)[:\s]*', '', phones[0], flags=re.IGNORECASE)
                if not phone.startswith(('070', '080', '090')):
                    return phone
        
        return None
    
    def extract_mobile(self, text):
        """携帯電話番号を抽出"""
        text_cleaned = text.replace(' ', '').replace('　', '')
        pattern = r'(?:Mobile|mobile|携帯|FAX)?[:\s]*0[789]0-?\d{4}-?\d{4}'
        mobiles = re.findall(pattern, text_cleaned, re.IGNORECASE)
        
        for mobile in mobiles:
            if 'FAX' not in mobile and 'fax' not in mobile:
                cleaned = re.sub(r'(?:Mobile|mobile|携帯)[:\s]*', '', mobile, flags=re.IGNORECASE)
                return cleaned
        
        return None
    
    def extract_name(self, text):
        """名前を抽出"""
        lines = text.split('\n')
        
        for line in lines[:5]:
            line = line.strip()
            if re.match(r'^[\u4E00-\u9FFF]{2,4}[\s　]+[\u4E00-\u9FFF]{1,4}$', line):
                return line
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line):
                return line
        
        return None
    
    def extract_company(self, text):
        """会社名を抽出"""
        keywords = [
            '株式会社', '有限会社', '合同会社', '合資会社',
            '社団法人', '財団法人', '医療法人',
            'Co.', 'Ltd.', 'Inc.', 'Corporation', 'Corp.',
            'K.K.', 'GK'
        ]
        
        lines = text.split('\n')
        
        for line in lines[:10]:
            for keyword in keywords:
                if keyword in line:
                    return line.strip()
        
        return None
    
    def extract_address(self, text):
        """住所を抽出"""
        zipcode_pattern = r'〒?\d{3}-?\d{4}'
        prefectures = [
            '北海道', '青森県', '岩手県', '宮城県', '秋田県', '山形県', '福島県',
            '茨城県', '栃木県', '群馬県', '埼玉県', '千葉県', '東京都', '神奈川県',
            '新潟県', '富山県', '石川県', '福井県', '山梨県', '長野県', '岐阜県',
            '静岡県', '愛知県', '三重県', '滋賀県', '京都府', '大阪府', '兵庫県',
            '奈良県', '和歌山県', '鳥取県', '島根県', '岡山県', '広島県', '山口県',
            '徳島県', '香川県', '愛媛県', '高知県', '福岡県', '佐賀県', '長崎県',
            '熊本県', '大分県', '宮崎県', '鹿児島県', '沖縄県'
        ]
        
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if re.search(zipcode_pattern, line) or any(pref in line for pref in prefectures):
                address = line
                if i + 1 < len(lines):
                    address += ' ' + lines[i + 1]
                return address.strip()
        
        return None
    
    def extract_website(self, text):
        """Webサイトを抽出"""
        patterns = [
            r'https?://[^\s]+',
            r'www\.[^\s]+',
            r'[a-zA-Z0-9.-]+\.(com|co\.jp|jp|net|org|info)'
        ]
        
        for pattern in patterns:
            websites = re.findall(pattern, text, re.IGNORECASE)
            if websites:
                return websites[0].strip()
        
        return None

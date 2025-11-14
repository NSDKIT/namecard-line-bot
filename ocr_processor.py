import os
from google.cloud import vision
import re

class OCRProcessor:
    def __init__(self, credentials_path=None):
        self.client = vision.ImageAnnotatorClient()
    
    def process_image(self, image_path):
        """画像から名刺情報を抽出（改良版）"""
        try:
            print(f"🔍 Processing: {image_path}")
            text = self.ocr_image(image_path)
            
            if not text or not text.strip():
                print("⚠️ No text detected")
                return None
            
            print(f"📝 Detected text:\n{text}\n")
            
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
            
            print(f"✅ Extracted:")
            print(f"  Name: {info.get('name', 'None')}")
            print(f"  Company: {info.get('company', 'None')}")
            print(f"  Email: {info.get('email', 'None')}")
            print(f"  Phone: {info.get('phone', 'None')}")
            
            return [info] if (info.get('name') or info.get('company')) else None
        
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
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
        """メールアドレスを抽出（改良版）"""
        # スペースを削除
        text_cleaned = text.replace(' ', '').replace('　', '')
        
        # パターン1: 標準的なメールアドレス
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text_cleaned)
        if emails:
            return emails[0]
        
        # パターン2: カンマやスペースで区切られている場合
        emails = re.findall(r'[a-zA-Z0-9._%+-]+[@＠][a-zA-Z0-9.-]+[\.。][a-zA-Z]{2,}', text_cleaned)
        if emails:
            return emails[0].replace('＠', '@').replace('。', '.')
        
        return None
    
    def extract_phone(self, text):
        """固定電話番号を抽出（改良版）"""
        text_cleaned = text.replace(' ', '').replace('　', '').replace('ー', '-').replace('−', '-')
        
        patterns = [
            r'(?:TEL|Tel|tel|電話|℡)[:\s：]*([0-9０-９]{2,4}[-ー－][0-9０-９]{2,4}[-ー－][0-9０-９]{4})',
            r'([0-9０-９]{2,4}[-ー－][0-9０-９]{2,4}[-ー－][0-9０-９]{4})',
            r'(?:TEL|Tel|tel|電話|℡)[:\s：]*([0-9０-９]{9,11})',
            r'\b([0-9０-９]{9,11})\b',
        ]
        
        for pattern in patterns:
            phones = re.findall(pattern, text_cleaned, re.IGNORECASE)
            if phones:
                phone = phones[0]
                # 全角数字を半角に変換
                phone = self.zen_to_han(phone)
                # 携帯番号は除外
                if not phone.startswith(('070', '080', '090')):
                    return phone
        
        return None
    
    def extract_mobile(self, text):
        """携帯電話番号を抽出（改良版）"""
        text_cleaned = text.replace(' ', '').replace('　', '').replace('ー', '-').replace('−', '-')
        
        patterns = [
            r'(?:Mobile|mobile|携帯|TEL|Tel)[:\s：]*([0-9０-９]{3}[-ー－][0-9０-９]{4}[-ー－][0-9０-９]{4})',
            r'([0-9０-９]{3}[-ー－][0-9０-９]{4}[-ー－][0-9０-９]{4})',
        ]
        
        for pattern in patterns:
            mobiles = re.findall(pattern, text_cleaned, re.IGNORECASE)
            for mobile in mobiles:
                if 'FAX' not in mobile and 'fax' not in mobile:
                    mobile = self.zen_to_han(mobile)
                    if mobile.startswith(('070', '080', '090')):
                        return mobile
        
        return None
    
    def extract_name(self, text):
        """名前を抽出（改良版）"""
        lines = text.split('\n')
        
        for i, line in enumerate(lines[:8]):
            line = line.strip()
            
            # パターン1: 日本語の名前（姓名の間にスペース）
            match = re.match(r'^([\u4E00-\u9FFF]{2,4})[\s　]+([\u4E00-\u9FFF]{1,4})$', line)
            if match:
                return f"{match.group(1)} {match.group(2)}"
            
            # パターン2: 日本語の名前（スペースなし）
            match = re.match(r'^([\u4E00-\u9FFF]{2,5})$', line)
            if match and i < 3:  # 最初の3行のみ
                # 次の行と組み合わせて判定
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if re.match(r'^[\u4E00-\u9FFF]{1,3}$', next_line):
                        return f"{line} {next_line}"
                return line
            
            # パターン3: 英語の名前
            match = re.match(r'^([A-Z][a-z]+)[\s　]+([A-Z][a-z]+)$', line)
            if match:
                return f"{match.group(1)} {match.group(2)}"
            
            # パターン4: ローマ字（ALL CAPS）
            match = re.match(r'^([A-Z]{2,})[\s　]+([A-Z]{2,})$', line)
            if match:
                return f"{match.group(1)} {match.group(2)}"
        
        return None
    
    def extract_company(self, text):
        """会社名を抽出（改良版）"""
        keywords = [
            '株式会社', '有限会社', '合同会社', '合資会社',
            '社団法人', '財団法人', '医療法人', '学校法人',
            'Co\.', 'Ltd\.', 'Inc\.', 'Corporation', 'Corp\.',
            'K\.K\.', 'GK', 'LLC', 'Limited'
        ]
        
        lines = text.split('\n')
        
        # キーワードを含む行を探す
        for line in lines[:15]:
            line = line.strip()
            for keyword in keywords:
                if re.search(keyword, line, re.IGNORECASE):
                    # 会社名として妥当な長さか確認
                    if 3 <= len(line) <= 100:
                        return line
        
        return None
    
    def extract_address(self, text):
        """住所を抽出（改良版）"""
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
            # 郵便番号または都道府県を含む行
            if re.search(r'[〒〠][0-9０-９]{3}[-ー－]?[0-9０-９]{4}', line) or any(pref in line for pref in prefectures):
                address = line
                # 次の行も住所の続きの可能性
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if not any(kw in next_line for kw in ['TEL', 'FAX', 'Email', '@', 'http']):
                        address += ' ' + next_line
                return address.strip()
        
        return None
    
    def extract_website(self, text):
        """Webサイトを抽出（改良版）"""
        patterns = [
            r'https?://[^\s]+',
            r'www\.[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
            r'[a-zA-Z0-9.-]+\.(com|co\.jp|jp|net|org|info|biz)'
        ]
        
        for pattern in patterns:
            websites = re.findall(pattern, text, re.IGNORECASE)
            if websites:
                return websites[0].strip()
        
        return None
    
    def zen_to_han(self, text):
        """全角数字を半角に変換"""
        zen = "０１２３４５６７８９"
        han = "0123456789"
        for z, h in zip(zen, han):
            text = text.replace(z, h)
        return text

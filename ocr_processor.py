import os
from google.cloud import vision
import re
from typing import List, Dict, Optional
import numpy as np
from sklearn.cluster import DBSCAN
from scipy.spatial.distance import cdist

class OCRProcessor:
    def __init__(self, credentials_path=None):
        self.client = vision.ImageAnnotatorClient()
    
    def process_image(self, image_path):
        """画像から名刺情報を抽出（複数枚対応 - 高度版）"""
        try:
            print(f"🔍 Processing: {image_path}")
            
            # テキストとレイアウト情報を取得
            text_blocks = self.ocr_image_with_layout(image_path)
            
            if not text_blocks:
                print("⚠️ No text detected")
                return []
            
            print(f"📝 Found {len(text_blocks)} text blocks")
            
            # DBSCANクラスタリングで名刺をグループ化
            namecard_groups = self.group_text_by_clustering(text_blocks)
            
            print(f"📇 Detected {len(namecard_groups)} namecard(s)")
            
            # 各名刺から情報を抽出
            results = []
            for i, group in enumerate(namecard_groups, 1):
                text = '\n'.join([block['text'] for block in group])
                info = self.extract_info_from_text(text)
                if info and (info.get('name') or info.get('company') or info.get('email')):
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
                            block_text += word_text + ' '
                        block_text += '\n'
                    
                    if block_text.strip():
                        text_blocks.append({
                            'text': block_text.strip(),
                            'x': sum(x_coords) / len(x_coords),
                            'y': sum(y_coords) / len(y_coords),
                            'min_x': min(x_coords),
                            'max_x': max(x_coords),
                            'min_y': min(y_coords),
                            'max_y': max(y_coords),
                            'width': max(x_coords) - min(x_coords),
                            'height': max(y_coords) - min(y_coords),
                            'vertices': vertices
                        })
            
            return text_blocks
        
        except Exception as e:
            print(f"❌ OCR Error: {e}")
            raise
    
    def group_text_by_clustering(self, text_blocks, max_cards=9):
        """DBSCANクラスタリングで名刺をグループ化"""
        if not text_blocks or len(text_blocks) == 0:
            return []
        
        # 単一ブロックの場合
        if len(text_blocks) == 1:
            return [text_blocks]
        
        # 座標データを準備
        coords = np.array([[block['x'], block['y']] for block in text_blocks])
        
        # 画像のスケールを推定（名刺サイズの推定）
        x_range = max([b['max_x'] for b in text_blocks]) - min([b['min_x'] for b in text_blocks])
        y_range = max([b['max_y'] for b in text_blocks]) - min([b['min_y'] for b in text_blocks])
        
        # 標準的な名刺サイズ: 91mm x 55mm (約 3.6 : 2.2)
        # epsを画像サイズに基づいて動的に設定
        eps = min(x_range, y_range) * 0.15  # 画像サイズの15%
        
        print(f"🔧 DBSCAN parameters: eps={eps:.1f}")
        
        # DBSCANクラスタリング実行
        clustering = DBSCAN(eps=eps, min_samples=1, metric='euclidean').fit(coords)
        labels = clustering.labels_
        
        # ノイズ（-1ラベル）は個別の名刺として扱う
        unique_labels = set(labels)
        
        print(f"📊 Found {len(unique_labels)} clusters")
        
        # クラスタごとにブロックをグループ化
        namecard_groups = []
        
        for label in unique_labels:
            cluster_indices = np.where(labels == label)[0]
            cluster_blocks = [text_blocks[i] for i in cluster_indices]
            
            # ブロック数が極端に少ない場合はスキップ（ノイズの可能性）
            if len(cluster_blocks) < 1:
                continue
            
            # クラスタの領域を計算
            cluster_min_x = min([b['min_x'] for b in cluster_blocks])
            cluster_max_x = max([b['max_x'] for b in cluster_blocks])
            cluster_min_y = min([b['min_y'] for b in cluster_blocks])
            cluster_max_y = max([b['max_y'] for b in cluster_blocks])
            
            cluster_width = cluster_max_x - cluster_min_x
            cluster_height = cluster_max_y - cluster_min_y
            
            # 名刺のアスペクト比チェック（横長の矩形であること）
            # 標準名刺: 91mm x 55mm = 1.65倍
            aspect_ratio = cluster_width / cluster_height if cluster_height > 0 else 0
            
            # アスペクト比が0.5〜4の範囲なら名刺として認識
            if 0.5 <= aspect_ratio <= 4.0:
                # Y座標でソート（上から下へ）
                cluster_blocks.sort(key=lambda b: b['y'])
                namecard_groups.append(cluster_blocks)
                print(f"  ✓ Cluster {label}: {len(cluster_blocks)} blocks, aspect={aspect_ratio:.2f}")
            else:
                print(f"  ✗ Cluster {label}: Invalid aspect ratio {aspect_ratio:.2f}")
        
        # 名刺を位置順にソート（左から右、上から下）
        namecard_groups.sort(key=lambda group: (
            min([b['y'] for b in group]),  # Y座標（行）
            min([b['x'] for b in group])   # X座標（列）
        ))
        
        # 最大9枚まで
        return namecard_groups[:max_cards]
    
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
        patterns = [
            r'(?:TEL|Tel|tel|電話)?[:\s]*0\d{1,4}-\d{1,4}-\d{4}',
            r'(?:TEL|Tel|tel|電話)?[:\s]*0\d{9,10}'
        ]
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
            # 日本語の名前（姓名の間にスペース）
            if re.match(r'^[\u4E00-\u9FFF]{2,4}[\s　]+[\u4E00-\u9FFF]{1,4}$', line):
                return line
            # 英語の名前
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line):
                return line
        return None
    
    def extract_company(self, text):
        keywords = [
            '株式会社', '有限会社', '合同会社', '合資会社',
            '社団法人', '財団法人', '医療法人',
            'Co.', 'Ltd.', 'Inc.', 'Corporation', 'Corp.',
            'K.K.', 'GK', 'LLC'
        ]
        lines = text.split('\n')
        for line in lines[:10]:
            for keyword in keywords:
                if keyword in line:
                    return line.strip()
        return None
    
    def extract_address(self, text):
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
            if re.search(r'〒?\d{3}-?\d{4}', line) or any(p in line for p in prefectures):
                address = line
                if i + 1 < len(lines):
                    address += ' ' + lines[i + 1]
                return address.strip()
        return None
    
    def extract_website(self, text):
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

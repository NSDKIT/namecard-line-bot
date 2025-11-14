import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    # LINE Bot設定
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
    LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET')
    
    # Supabase設定
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # Google Cloud設定
    GOOGLE_APPLICATION_CREDENTIALS = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'google-credentials.json')
    
    # 本番環境の場合、Base64エンコードされた認証情報を使用
    if not os.path.exists(GOOGLE_APPLICATION_CREDENTIALS) and os.getenv('GOOGLE_CREDENTIALS_BASE64'):
        try:
            credentials_json = base64.b64decode(os.getenv('GOOGLE_CREDENTIALS_BASE64')).decode('utf-8')
            # 一時ファイルに書き込み
            with open('/tmp/google-credentials.json', 'w') as f:
                f.write(credentials_json)
            GOOGLE_APPLICATION_CREDENTIALS = '/tmp/google-credentials.json'
            print("✅ Google credentials loaded from environment variable")
        except Exception as e:
            print(f"❌ Error loading Google credentials: {e}")
    
    # Flask設定
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    
    @staticmethod
    def validate():
        """必須の環境変数がセットされているか確認"""
        required = [
            'LINE_CHANNEL_ACCESS_TOKEN',
            'LINE_CHANNEL_SECRET',
            'SUPABASE_URL',
            'SUPABASE_KEY'
        ]
        missing = [var for var in required if not os.getenv(var)]
        if missing:
            raise ValueError(f"Missing environment variables: {', '.join(missing)}")
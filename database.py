from supabase import create_client, Client
import os
from datetime import datetime

class Database:
    def __init__(self):
        """Supabaseクライアントを初期化"""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        
        self.client: Client = create_client(supabase_url, supabase_key)
        print("✅ Supabase connected")
    
    def get_or_create_user(self, line_user_id: str, display_name: str = None):
        """ユーザーを取得または作成"""
        try:
            # ユーザーを検索
            response = self.client.table('users')\
                .select('*')\
                .eq('line_user_id', line_user_id)\
                .execute()
            
            if response.data:
                print(f"👤 User found: {line_user_id}")
                return response.data[0]
            
            # 新規ユーザー作成
            new_user = {
                'line_user_id': line_user_id,
                'display_name': display_name,
                'plan': 'free',
                'monthly_usage': 0
            }
            
            response = self.client.table('users').insert(new_user).execute()
            print(f"👤 New user created: {line_user_id}")
            return response.data[0]
        
        except Exception as e:
            print(f"❌ Error in get_or_create_user: {e}")
            return None
    
    def save_namecard(self, user_id: str, namecard_data: dict):
        """名刺データを保存"""
        try:
            namecard = {
                'user_id': user_id,
                'name': namecard_data.get('name'),
                'company': namecard_data.get('company'),
                'email': namecard_data.get('email'),
                'phone': namecard_data.get('phone'),
                'mobile': namecard_data.get('mobile'),
                'address': namecard_data.get('address'),
                'website': namecard_data.get('website'),
                'full_text': namecard_data.get('full_text')
            }
            
            response = self.client.table('namecards').insert(namecard).execute()
            print(f"💾 Namecard saved: {namecard.get('name')}")
            return response.data[0] if response.data else None
        
        except Exception as e:
            print(f"❌ Error in save_namecard: {e}")
            return None
    
    def get_user_namecards(self, user_id: str, limit: int = 10):
        """ユーザーの名刺一覧を取得（最新順）"""
        try:
            response = self.client.table('namecards')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data
        
        except Exception as e:
            print(f"❌ Error in get_user_namecards: {e}")
            return []
    
    def search_namecards(self, user_id: str, keyword: str):
        """名刺を検索"""
        try:
            # Supabaseの検索機能を使用
            response = self.client.table('namecards')\
                .select('*')\
                .eq('user_id', user_id)\
                .or_(f'name.ilike.%{keyword}%,company.ilike.%{keyword}%,email.ilike.%{keyword}%')\
                .execute()
            
            return response.data
        
        except Exception as e:
            print(f"❌ Error in search_namecards: {e}")
            return []
    
    def get_all_user_namecards(self, user_id: str):
        """ユーザーの全名刺を取得"""
        try:
            response = self.client.table('namecards')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .execute()
            
            return response.data
        
        except Exception as e:
            print(f"❌ Error in get_all_user_namecards: {e}")
            return []
    
    def delete_namecard(self, namecard_id: str, user_id: str):
        """名刺を削除（ユーザー確認付き）"""
        try:
            response = self.client.table('namecards')\
                .delete()\
                .eq('id', namecard_id)\
                .eq('user_id', user_id)\
                .execute()
            
            return True
        
        except Exception as e:
            print(f"❌ Error in delete_namecard: {e}")
            return False
    
    def increment_monthly_usage(self, user_id: str):
        """月間使用回数を増やす"""
        try:
            # 現在の使用回数を取得
            response = self.client.table('users')\
                .select('monthly_usage')\
                .eq('id', user_id)\
                .execute()
            
            if response.data:
                current_usage = response.data[0].get('monthly_usage', 0)
                
                # 使用回数を+1
                self.client.table('users')\
                    .update({'monthly_usage': current_usage + 1})\
                    .eq('id', user_id)\
                    .execute()
            
            return True
        
        except Exception as e:
            print(f"❌ Error in increment_monthly_usage: {e}")
            return False
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage
)
import os
import tempfile
import base64
from dotenv import load_dotenv
from ocr_processor import OCRProcessor
from database import Database

load_dotenv()

app = Flask(__name__)

LINE_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# Google認証情報をBase64から復元
if os.getenv('GOOGLE_CREDENTIALS_BASE64'):
    try:
        credentials_json = base64.b64decode(os.getenv('GOOGLE_CREDENTIALS_BASE64')).decode('utf-8')
        with open('/tmp/google-credentials.json', 'w') as f:
            f.write(credentials_json)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = '/tmp/google-credentials.json'
        print("✅ Google credentials loaded from environment variable")
    except Exception as e:
        print(f"❌ Error loading Google credentials: {e}")
else:
    print("⚠️ GOOGLE_CREDENTIALS_BASE64 not found in environment variables")

# OCRとデータベースを初期化
try:
    ocr = OCRProcessor()
    db = Database()
    print("✅ Supabase connected")
    print("✅ OCR and Database initialized")
except Exception as e:
    print(f"❌ Initialization error: {e}")
    import traceback
    traceback.print_exc()
    ocr = None
    db = None

@app.route("/")
def hello():
    return "Namecard Reader Bot is running! v5.0 - Simple OCR"

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        print(f"❌ Error: {e}")
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    user_message = event.message.text
    line_user_id = event.source.user_id
    
    try:
        if not db:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="システムエラー：データベースが利用できません")
            )
            return
        
        profile = line_bot_api.get_profile(line_user_id)
        user = db.get_or_create_user(line_user_id, profile.display_name)
        
        if user_message == "使い方" or user_message == "ヘルプ":
            reply_text = """📇 名刺読み取りBotの使い方

【基本的な使い方】
1. 名刺の写真を撮影
2. このトークに画像を送信
3. 自動で名刺を読み取って保存！

【コマンド】
- 使い方 - このメッセージ
- 一覧 - 最新10件の名刺
- 検索 [キーワード] - 名刺を検索
- テスト - 動作確認

さっそく名刺を送ってみてください！📸"""
        
        elif user_message == "一覧":
            namecards = db.get_user_namecards(user['id'], limit=10)
            
            if not namecards:
                reply_text = "まだ名刺が登録されていません。\n名刺の写真を送ってください！"
            else:
                reply_text = f"📇 保存済み名刺（最新{len(namecards)}件）\n\n"
                
                for i, card in enumerate(namecards, 1):
                    reply_text += f"【{i}】\n"
                    if card.get('name'):
                        reply_text += f"👤 {card['name']}\n"
                    if card.get('company'):
                        reply_text += f"🏢 {card['company']}\n"
                    if card.get('email'):
                        reply_text += f"📧 {card['email']}\n"
                    if card.get('phone'):
                        reply_text += f"📞 {card['phone']}\n"
                    reply_text += "\n"
        
        elif user_message.startswith("検索 "):
            keyword = user_message[3:].strip()
            
            if not keyword:
                reply_text = "検索キーワードを入力してください。\n例: 検索 山田"
            else:
                namecards = db.search_namecards(user['id'], keyword)
                
                if not namecards:
                    reply_text = f"「{keyword}」に一致する名刺が見つかりませんでした。"
                else:
                    reply_text = f"🔍 検索結果: {len(namecards)}件\n\n"
                    
                    for i, card in enumerate(namecards[:10], 1):
                        reply_text += f"【{i}】\n"
                        if card.get('name'):
                            reply_text += f"�� {card['name']}\n"
                        if card.get('company'):
                            reply_text += f"🏢 {card['company']}\n"
                        reply_text += "\n"
        
        elif user_message == "テスト":
            reply_text = "✅ システム正常動作中！\n\n名刺の写真を送ってみてください。"
        
        else:
            reply_text = f"受信: {user_message}\n\n「使い方」で使い方を表示"
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
    
    except Exception as e:
        print(f"❌ Text error: {e}")
        import traceback
        traceback.print_exc()

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """画像メッセージの処理（修正版）"""
    line_user_id = event.source.user_id
    
    try:
        if not ocr or not db:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="システムエラー：OCRまたはデータベースが利用できません")
            )
            return
        
        profile = line_bot_api.get_profile(line_user_id)
        user = db.get_or_create_user(line_user_id, profile.display_name)
        
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📸 画像を受信しました！\n名刺を読み取り中です...\n\n⏳ 10-15秒ほどお待ちください。")
        )
        
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            for chunk in message_content.iter_content():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # OCR処理
        result = ocr.process_image(temp_file_path)
        
        if not result:
            result_text = "❌ 名刺からテキストを検出できませんでした。"
        else:
            # resultがリストの場合、最初の要素を取得
            if isinstance(result, list):
                card_info = result[0] if len(result) > 0 else None
            else:
                card_info = result
            
            if not card_info:
                result_text = "❌ 名刺情報を抽出できませんでした。"
            else:
                # データベースに保存
                saved = db.save_namecard(user['id'], card_info)
                
                if saved:
                    db.increment_monthly_usage(user['id'])
                    
                    result_text = "✅ 名刺を読み取って保存しました！\n\n"
                    
                    if card_info.get('name'):
                        result_text += f"👤 名前: {card_info['name']}\n"
                    if card_info.get('company'):
                        result_text += f"🏢 会社: {card_info['company']}\n"
                    if card_info.get('email'):
                        result_text += f"📧 メール: {card_info['email']}\n"
                    if card_info.get('phone'):
                        result_text += f"📞 電話: {card_info['phone']}\n"
                    if card_info.get('mobile'):
                        result_text += f"📱 携帯: {card_info['mobile']}\n"
                    
                    result_text += "\n💾 データベースに保存しました\n「一覧」で確認できます"
                else:
                    result_text = "❌ データベースへの保存に失敗しました。"
        
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=result_text)
        )
        
        os.unlink(temp_file_path)
        
    except Exception as e:
        print(f"❌ Image error: {e}")
        import traceback
        traceback.print_exc()
        
        try:
            line_bot_api.push_message(
                line_user_id,
                TextSendMessage(text=f"❌ エラーが発生しました。\nもう一度お試しください。")
            )
        except:
            pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🚀 Namecard Bot Starting on port {port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)

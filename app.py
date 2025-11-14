from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage
)
import os
import tempfile
from dotenv import load_dotenv
from ocr_processor import OCRProcessor
from database import Database

load_dotenv()

app = Flask(__name__)

LINE_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_SECRET = os.getenv('LINE_CHANNEL_SECRET')

line_bot_api = LineBotApi(LINE_TOKEN)
handler = WebhookHandler(LINE_SECRET)

# OCRとデータベースを初期化
ocr = OCRProcessor(credentials_path='google-credentials.json')
db = Database()

@app.route("/")
def hello():
    return "Namecard Reader Bot is running! v4.0 with Database"

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
        # ユーザー情報取得
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
- 全件 - 全ての名刺
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
        
        elif user_message == "全件":
            namecards = db.get_all_user_namecards(user['id'])
            
            if not namecards:
                reply_text = "まだ名刺が登録されていません。"
            else:
                reply_text = f"📇 全名刺（{len(namecards)}件）\n\n"
                
                for i, card in enumerate(namecards, 1):
                    reply_text += f"【{i}】"
                    if card.get('name'):
                        reply_text += f" {card['name']}"
                    if card.get('company'):
                        reply_text += f" / {card['company']}"
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
                            reply_text += f"👤 {card['name']}\n"
                        if card.get('company'):
                            reply_text += f"🏢 {card['company']}\n"
                        if card.get('email'):
                            reply_text += f"📧 {card['email']}\n"
                        reply_text += "\n"
                    
                    if len(namecards) > 10:
                        reply_text += f"\n※ 他{len(namecards) - 10}件"
        
        elif user_message == "テスト":
            reply_text = "✅ OCR + データベース機能が有効です！"
        
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
    """画像メッセージの処理"""
    line_user_id = event.source.user_id
    
    try:
        # ユーザー情報取得
        profile = line_bot_api.get_profile(line_user_id)
        user = db.get_or_create_user(line_user_id, profile.display_name)
        
        # 処理中メッセージ
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="📸 画像を受信しました！\n名刺を読み取り中です...\n\n⏳ 10-15秒ほどお待ちください。")
        )
        
        # 画像をダウンロード
        message_id = event.message.id
        message_content = line_bot_api.get_message_content(message_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            for chunk in message_content.iter_content():
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        # OCR処理
        card_info = ocr.process_image(temp_file_path)
        
        if not card_info:
            result_text = "❌ 名刺からテキストを検出できませんでした。"
        else:
            # データベースに保存
            saved = db.save_namecard(user['id'], card_info)
            
            if saved:
                # 使用回数を増やす
                db.increment_monthly_usage(user['id'])
                
                # 結果を整形
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
        
        # 結果を送信
        line_bot_api.push_message(
            line_user_id,
            TextSendMessage(text=result_text)
        )
        
        # 一時ファイル削除
        os.unlink(temp_file_path)
        
    except Exception as e:
        print(f"❌ Image error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("\n" + "=" * 60)
    print(f"🚀 Namecard Bot with Database")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)  # 本番環境では0.0.0.0
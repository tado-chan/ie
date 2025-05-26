import json
import os
import uuid
from datetime import datetime

def lambda_handler(event, context):
    """
    シンプルな入力ハンドラー（テスト用）
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # リクエストボディの解析
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "")
        
        # 会話IDの生成
        conversation_id = str(uuid.uuid4())
        
        # レスポンスの作成
        response_body = {
            "conversationId": conversation_id,
            "status": "received",
            "message": f"メッセージを受信しました: {message}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
            "body": json.dumps(response_body, ensure_ascii=False)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
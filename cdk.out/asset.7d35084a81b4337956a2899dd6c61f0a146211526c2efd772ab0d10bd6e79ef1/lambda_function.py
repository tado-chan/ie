import json
import os
import uuid
from datetime import datetime
import boto3

# Step Functionsクライアント
stepfunctions = boto3.client('stepfunctions')

# 環境変数
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN', '')

def lambda_handler(event, context):
    """
    入力を受け取り、Step Functionsを開始する
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # リクエストボディの解析
        body = json.loads(event.get("body", "{}"))
        message = body.get("message", "")
        
        # 会話IDの生成
        conversation_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        # Step Functionsを開始する場合
        if STATE_MACHINE_ARN:
            try:
                # Step Functions実行
                execution = stepfunctions.start_execution(
                    stateMachineArn=STATE_MACHINE_ARN,
                    name=f"chat-{conversation_id}",
                    input=json.dumps({
                        "conversationId": conversation_id,
                        "message": message,
                        "timestamp": timestamp
                    })
                )
                
                response_body = {
                    "conversationId": conversation_id,
                    "status": "processing",
                    "message": "分析を開始しました",
                    "executionArn": execution['executionArn'],
                    "timestamp": timestamp
                }
                status_code = 202  # Accepted
                
            except Exception as e:
                print(f"Step Functions error: {str(e)}")
                # Step Functionsが失敗した場合は通常のレスポンス
                response_body = {
                    "conversationId": conversation_id,
                    "status": "received",
                    "message": f"メッセージを受信しました: {message}",
                    "timestamp": timestamp
                }
                status_code = 200
        else:
            # Step Functionsが設定されていない場合
            response_body = {
                "conversationId": conversation_id,
                "status": "received",
                "message": f"メッセージを受信しました: {message}",
                "timestamp": timestamp
            }
            status_code = 200
        
        return {
            "statusCode": status_code,
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
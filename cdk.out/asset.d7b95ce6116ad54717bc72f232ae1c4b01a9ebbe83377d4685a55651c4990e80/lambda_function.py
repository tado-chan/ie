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
        # HTTPメソッドをチェック
        http_method = event.get("httpMethod", "")
        
        if http_method == "GET":
            # GET リクエスト - 会話履歴取得（簡易実装）
            return handle_get_conversation(event)
        elif http_method == "POST":
            # POST リクエスト - メッセージ送信
            return handle_post_message(event)
        else:
            return {
                "statusCode": 405,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({"error": "Method not allowed"})
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

def handle_post_message(event):
    """POSTリクエスト - メッセージ送信処理"""
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

def handle_get_conversation(event):
    """GETリクエスト - 会話履歴取得処理（簡易実装）"""
    conversation_id = event.get('pathParameters', {}).get('conversationId')
    
    if not conversation_id:
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({"error": "conversationId is required"})
        }
    
    # 簡易実装：実際のDBからの取得は後で実装
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        },
        "body": json.dumps({
            "conversationId": conversation_id,
            "status": "found",
            "message": "会話履歴取得機能は実装中です"
        })
    }
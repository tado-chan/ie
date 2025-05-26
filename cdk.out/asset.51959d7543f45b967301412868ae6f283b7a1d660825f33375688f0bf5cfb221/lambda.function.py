# src/lambda/api/status_handler/lambda_function.py
import json
import os
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    会話IDに基づいてStep Functionsの実行結果を取得する
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # パスパラメータから会話IDを取得
        conversation_id = event.get('pathParameters', {}).get('conversationId')
        
        if not conversation_id:
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "error": "conversationId is required"
                })
            }
        
        # デバッグ情報を追加
        # AWS_REGIONは Lambda実行時に自動的に設定される
        region = os.environ.get('AWS_REGION')  # これは自動的に利用可能
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        
        print(f"Region: {region}")
        print(f"State Machine ARN: {state_machine_arn}")
        print(f"Conversation ID: {conversation_id}")
        
        # 簡易レスポンス（デバッグ用）
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "conversationId": conversation_id,
                "status": "processing",
                "message": "Status Handler が正常に動作しています",
                "debug": {
                    "region": region,
                    "hasStateMachineArn": bool(state_machine_arn),
                    "stateMachineArn": state_machine_arn[:50] + "..." if state_machine_arn else None
                },
                "timestamp": "2025-05-26T19:47:32.000Z"
            })
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
                "details": str(e)
            })
        }
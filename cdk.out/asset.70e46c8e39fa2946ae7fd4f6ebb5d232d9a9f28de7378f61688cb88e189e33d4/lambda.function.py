# src/lambda/api/status_handler/lambda_function.py を以下に置き換え
import json
import os
import boto3
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    """
    会話IDに基づいてStep Functionsの実行結果を取得する（デバッグ版）
    """
    print(f"Event: {json.dumps(event)}")
    print(f"Context: {context}")
    print(f"Environment variables: {dict(os.environ)}")
    
    try:
        # パスパラメータから会話IDを取得
        conversation_id = event.get('pathParameters', {}).get('conversationId')
        print(f"Extracted conversationId: {conversation_id}")
        
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
        
        # デバッグ: Step Functions クライアント作成
        stepfunctions = boto3.client('stepfunctions')
        print("Step Functions client created successfully")
        
        # executionArn を構築
        execution_arn = construct_execution_arn(conversation_id)
        print(f"Constructed execution ARN: {execution_arn}")
        
        if not execution_arn:
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "conversationId": conversation_id,
                    "status": "error",
                    "error": "Could not construct execution ARN",
                    "debug": {
                        "region": os.environ.get('AWS_REGION'),
                        "state_machine_arn": os.environ.get('STATE_MACHINE_ARN')
                    }
                })
            }
        
        # Step Functions の実行状態を取得
        try:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
            status = response['status']
            print(f"Step Functions status: {status}")
            
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "conversationId": conversation_id,
                    "status": "processing" if status == "RUNNING" else "completed" if status == "SUCCEEDED" else "error",
                    "stepFunctionsStatus": status,
                    "executionArn": execution_arn,
                    "debug": "Success"
                })
            }
        except ClientError as e:
            print(f"ClientError: {e}")
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "conversationId": conversation_id,
                    "status": "error",
                    "error": f"ClientError: {str(e)}",
                    "executionArn": execution_arn
                })
            }
            
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "details": str(e),
                "conversationId": conversation_id if 'conversation_id' in locals() else None
            })
        }

def construct_execution_arn(conversation_id):
    """executionArn を構築"""
    try:
        region = os.environ.get('AWS_REGION')
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        
        print(f"Region: {region}")
        print(f"State Machine ARN: {state_machine_arn}")
        
        if not region or not state_machine_arn:
            return None
            
        # アカウントIDとState Machine名を抽出
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        state_machine_name = state_machine_arn.split(':')[-1]
        
        execution_name = f"chat-{conversation_id}"
        execution_arn = f"arn:aws:states:{region}:{account_id}:execution:{state_machine_name}:{execution_name}"
        
        return execution_arn
    except Exception as e:
        print(f"Error constructing execution ARN: {e}")
        return None
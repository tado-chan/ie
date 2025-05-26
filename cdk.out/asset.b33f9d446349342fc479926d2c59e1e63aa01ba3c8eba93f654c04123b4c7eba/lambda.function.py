import json
import os
import boto3
from botocore.exceptions import ClientError

# Step Functionsクライアント
stepfunctions = boto3.client('stepfunctions')

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
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
                    "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
                },
                "body": json.dumps({
                    "error": "conversationId is required"
                })
            }
        
        # executionArnを構築（命名規則から）
        execution_arn = construct_execution_arn(conversation_id)
        
        if not execution_arn:
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*"
                },
                "body": json.dumps({
                    "conversationId": conversation_id,
                    "status": "error",
                    "error": "Execution not found"
                })
            }
        
        # Step Functionsの実行状態を取得
        try:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
            
            status = response['status']  # RUNNING, SUCCEEDED, FAILED, TIMED_OUT, ABORTED
            
            if status == 'RUNNING':
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "conversationId": conversation_id,
                        "status": "processing",
                        "message": "分析中です..."
                    })
                }
            elif status == 'SUCCEEDED':
                # 実行結果を取得
                output = json.loads(response.get('output', '{}'))
                
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "conversationId": conversation_id,
                        "status": "completed",
                        "analysis": output.get('analysis', ''),
                        "category": output.get('category', ''),
                        "recommendedRecipient": output.get('recommendedRecipient', ''),
                        "timestamp": response.get('stopDate', '').isoformat() if response.get('stopDate') else None
                    })
                }
            else:
                # FAILED, TIMED_OUT, ABORTED
                error_message = response.get('error', f'Execution {status}')
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "conversationId": conversation_id,
                        "status": "error",
                        "error": error_message
                    })
                }
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ExecutionDoesNotExist':
                return {
                    "statusCode": 404,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "conversationId": conversation_id,
                        "status": "error",
                        "error": "Execution not found"
                    })
                }
            else:
                raise e
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "conversationId": conversation_id,
                "status": "error",
                "error": "Internal server error"
            })
        }

def construct_execution_arn(conversation_id):
    """
    命名規則からexecutionArnを構築
    """
    try:
        region = os.environ.get('AWS_REGION', 'us-east-1')
        # アカウントIDを取得（Lambdaのcontextから）
        account_id = os.environ.get('AWS_ACCOUNT_ID')
        if not account_id:
            # contextから取得を試みる（実際のLambda実行時に利用可能）
            sts = boto3.client('sts')
            account_id = sts.get_caller_identity()['Account']
        
        # State Machine名を環境変数から取得
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        if state_machine_arn:
            # ARNからState Machine名を抽出
            state_machine_name = state_machine_arn.split(':')[-1]
        else:
            return None
            
        execution_name = f"chat-{conversation_id}"
        execution_arn = f"arn:aws:states:{region}:{account_id}:execution:{state_machine_name}:{execution_name}"
        
        print(f"Constructed execution ARN: {execution_arn}")
        return execution_arn
    except Exception as e:
        print(f"Error constructing execution ARN: {str(e)}")
        return None
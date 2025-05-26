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
        
        # executionArnを構築
        execution_arn = construct_execution_arn(conversation_id)
        
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
                    "error": "Could not construct execution ARN"
                })
            }
        
        # Step Functionsクライアント作成
        stepfunctions = boto3.client('stepfunctions')
        
        # Step Functionsの実行状態を取得
        try:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
            
            status = response['status']  # RUNNING, SUCCEEDED, FAILED, TIMED_OUT, ABORTED
            print(f"Step Functions status: {status}")
            
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
            print(f"ClientError: {error_code} - {str(e)}")
            
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
                return {
                    "statusCode": 200,
                    "headers": {
                        "Content-Type": "application/json",
                        "Access-Control-Allow-Origin": "*"
                    },
                    "body": json.dumps({
                        "conversationId": conversation_id,
                        "status": "error",
                        "error": f"AWS Error: {error_code}"
                    })
                }
        
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "conversationId": conversation_id if 'conversation_id' in locals() else 'unknown',
                "status": "error",
                "error": "Internal server error"
            })
        }

def construct_execution_arn(conversation_id):
    """
    命名規則からexecutionArnを構築
    """
    try:
        # AWS_REGIONは自動的に設定される
        region = os.environ.get('AWS_REGION')
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        
        print(f"Region: {region}")
        print(f"State Machine ARN: {state_machine_arn}")
        
        if not region or not state_machine_arn:
            print("Missing region or state machine ARN")
            return None
            
        # アカウントIDとState Machine名を抽出
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        state_machine_name = state_machine_arn.split(':')[-1]
        
        execution_name = f"chat-{conversation_id}"
        execution_arn = f"arn:aws:states:{region}:{account_id}:execution:{state_machine_name}:{execution_name}"
        
        print(f"Constructed execution ARN: {execution_arn}")
        return execution_arn
    except Exception as e:
        print(f"Error constructing execution ARN: {str(e)}")
        return None
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

# Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS Clients
stepfunctions = boto3.client("stepfunctions")
dynamodb = boto3.resource("dynamodb")

# Environment variables
STATE_MACHINE_ARN = os.environ["STATE_MACHINE_ARN"]
CONVERSATIONS_TABLE = os.environ["CONVERSATIONS_TABLE"]
WEBSOCKET_ENDPOINT = os.environ.get("WEBSOCKET_ENDPOINT", "")

# DynamoDB table
conversations_table = dynamodb.Table(CONVERSATIONS_TABLE)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    チャットボットへの入力を処理し、Step Functionsワークフローを開始する
    
    Args:
        event: API Gatewayからのイベント
        context: Lambda実行コンテキスト
    
    Returns:
        API Gatewayレスポンス
    """
    try:
        # リクエストボディの解析
        body = json.loads(event.get("body", "{}"))
        
        # 入力検証
        if not body.get("message"):
            return create_response(400, {"error": "メッセージが必要です"})
        
        # ユーザー情報の取得（Cognito認証済みの場合）
        user_info = extract_user_info(event)
        
        # 会話IDの生成
        conversation_id = str(uuid.uuid4())
        
        # WebSocket接続IDの取得（WebSocket経由の場合）
        connection_id = event.get("requestContext", {}).get("connectionId")
        
        # 会話レコードの作成
        conversation_record = create_conversation_record(
            conversation_id=conversation_id,
            user_info=user_info,
            message=body["message"],
            connection_id=connection_id
        )
        
        # DynamoDBに保存
        save_conversation(conversation_record)
        
        # Step Functions実行パラメータの準備
        state_machine_input = {
            "conversationId": conversation_id,
            "message": body["message"],
            "userInfo": user_info,
            "connectionId": connection_id,
            "context": body.get("context", {}),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Step Functionsワークフローを開始
        execution_arn = start_step_function(conversation_id, state_machine_input)
        
        # メトリクスの記録
        metrics.add_metric(name="ConversationStarted", unit=MetricUnit.Count, value=1)
        
        # レスポンスの作成
        response_body = {
            "conversationId": conversation_id,
            "status": "processing",
            "message": "ご相談を受け付けました。分析中です...",
            "executionArn": execution_arn
        }
        
        return create_response(202, response_body)
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        return create_response(400, {"error": str(e)})
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        metrics.add_metric(name="ConversationError", unit=MetricUnit.Count, value=1)
        return create_response(500, {"error": "内部エラーが発生しました"})


@tracer.capture_method
def extract_user_info(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    イベントからユーザー情報を抽出
    
    Args:
        event: API Gatewayイベント
    
    Returns:
        ユーザー情報の辞書
    """
    claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})
    
    return {
        "userId": claims.get("sub", "anonymous"),
        "email": claims.get("email", ""),
        "department": claims.get("custom:department", ""),
        "role": claims.get("custom:role", ""),
        "name": claims.get("name", "")
    }


@tracer.capture_method
def create_conversation_record(
    conversation_id: str,
    user_info: Dict[str, Any],
    message: str,
    connection_id: str = None
) -> Dict[str, Any]:
    """
    会話レコードを作成
    
    Args:
        conversation_id: 会話ID
        user_info: ユーザー情報
        message: メッセージ
        connection_id: WebSocket接続ID
    
    Returns:
        会話レコード
    """
    return {
        "conversationId": conversation_id,
        "userId": user_info["userId"],
        "userInfo": user_info,
        "initialMessage": message,
        "status": "initialized",
        "connectionId": connection_id,
        "createdAt": datetime.utcnow().isoformat(),
        "updatedAt": datetime.utcnow().isoformat(),
        "ttl": int((datetime.utcnow().timestamp())) + 86400 * 7  # 7日間保持
    }


@tracer.capture_method
def save_conversation(record: Dict[str, Any]) -> None:
    """
    会話レコードをDynamoDBに保存
    
    Args:
        record: 会話レコード
    """
    conversations_table.put_item(Item=record)
    logger.info(f"Conversation saved: {record['conversationId']}")


@tracer.capture_method
def start_step_function(
    conversation_id: str, 
    state_machine_input: Dict[str, Any]
) -> str:
    """
    Step Functionsワークフローを開始
    
    Args:
        conversation_id: 会話ID
        state_machine_input: ステートマシンの入力
    
    Returns:
        実行ARN
    """
    response = stepfunctions.start_execution(
        stateMachineArn=STATE_MACHINE_ARN,
        name=f"conversation-{conversation_id}",
        input=json.dumps(state_machine_input)
    )
    
    logger.info(f"Step Function started: {response['executionArn']}")
    return response['executionArn']


def create_response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    """
    API Gatewayレスポンスを作成
    
    Args:
        status_code: HTTPステータスコード
        body: レスポンスボディ
    
    Returns:
        API Gatewayレスポンス
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
            "Access-Control-Allow-Methods": "OPTIONS,POST"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }
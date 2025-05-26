# src/lambda/processors/websocket_connect/lambda_function.py
import json
import boto3
import os

# DynamoDB設定（接続管理用）
dynamodb = boto3.resource('dynamodb')
# 後でテーブル名を環境変数から取得
# table = dynamodb.Table(os.environ.get('CONNECTIONS_TABLE', ''))

def lambda_handler(event, context):
    """WebSocket接続時の処理"""
    print(f"Connect Event: {json.dumps(event)}")
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # 接続情報をDynamoDBに保存（後で実装）
        # table.put_item(Item={
        #     'connectionId': connection_id,
        #     'timestamp': datetime.utcnow().isoformat()
        # })
        
        return {
            'statusCode': 200,
            'body': 'Connected'
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

# src/lambda/processors/websocket_disconnect/lambda_function.py
import json
import boto3
import os

def lambda_handler(event, context):
    """WebSocket切断時の処理"""
    print(f"Disconnect Event: {json.dumps(event)}")
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # 接続情報をDynamoDBから削除（後で実装）
        return {
            'statusCode': 200,
            'body': 'Disconnected'
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

# src/lambda/processors/websocket_message/lambda_function.py
import json
import boto3
import os

def lambda_handler(event, context):
    """WebSocketメッセージ受信時の処理"""
    print(f"Message Event: {json.dumps(event)}")
    
    connection_id = event['requestContext']['connectionId']
    
    try:
        # メッセージ処理（必要に応じて実装）
        return {
            'statusCode': 200,
            'body': 'Message received'
        }
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }

# src/lambda/processors/websocket_sender/lambda_function.py
import json
import boto3
import os

# API Gateway Management API
apigateway_management_api = None

def lambda_handler(event, context):
    """WebSocketでメッセージを送信"""
    print(f"Sender Event: {json.dumps(event)}")
    
    global apigateway_management_api
    
    try:
        # Step Functionsから受け取ったデータ
        conversation_id = event.get('conversationId', '')
        analysis = event.get('analysis', '')
        
        # WebSocket接続ID（実際は接続管理テーブルから取得）
        # 今回は環境変数やイベントから取得する想定
        connection_id = event.get('connectionId', '')
        websocket_url = event.get('websocketUrl', os.environ.get('WEBSOCKET_URL', ''))
        
        if not connection_id or not websocket_url:
            print("Connection ID or WebSocket URL not found")
            return {'statusCode': 400, 'body': 'Missing connection info'}
        
        # API Gateway Management APIクライアント初期化
        if not apigateway_management_api:
            apigateway_management_api = boto3.client(
                'apigatewaymanagementapi',
                endpoint_url=websocket_url
            )
        
        # クライアントに送信するメッセージ
        message = {
            'conversationId': conversation_id,
            'analysis': analysis,
            'status': 'completed',
            'type': 'analysis'
        }
        
        # WebSocketでメッセージ送信
        apigateway_management_api.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(message, ensure_ascii=False)
        )
        
        return {
            'statusCode': 200,
            'body': 'Message sent successfully'
        }
        
    except Exception as e:
        print(f"Error sending WebSocket message: {str(e)}")
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }
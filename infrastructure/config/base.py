"""
基本設定ファイル
全環境で共通の設定を定義
"""
from typing import Dict, Any


class BaseConfig:
    """基本設定クラス"""
    
    # アプリケーション基本情報
    APP_NAME = "houkokusou-chatbot"
    APP_DESCRIPTION = "社内報連相サポートチャットボット"
    
    # Lambda設定
    LAMBDA_RUNTIME = "python3.11"
    LAMBDA_TIMEOUT_SECONDS = 30
    LAMBDA_MEMORY_SIZE = 512
    
    # Bedrock設定
    BEDROCK_MODEL_ID = "anthropic.claude-3-sonnet-20240229-v1:0"
    BEDROCK_MAX_TOKENS = 2000
    BEDROCK_TEMPERATURE = 0.7
    
    # DynamoDB設定
    DYNAMODB_BILLING_MODE = "PAY_PER_REQUEST"
    DYNAMODB_REMOVAL_POLICY = "DESTROY"  # 本番環境では"RETAIN"に変更
    
    # API Gateway設定
    API_GATEWAY_THROTTLE_RATE_LIMIT = 100
    API_GATEWAY_THROTTLE_BURST_LIMIT = 200
    
    # WebSocket設定
    WEBSOCKET_ROUTE_SELECTION_EXPRESSION = "$request.body.action"
    
    # Cognito設定
    COGNITO_PASSWORD_POLICY = {
        "min_length": 8,
        "require_lowercase": True,
        "require_uppercase": True,
        "require_digits": True,
        "require_symbols": True,
    }
    
    # CloudWatch設定
    LOG_RETENTION_DAYS = 7
    ALARM_EVALUATION_PERIODS = 1
    ALARM_THRESHOLD_PERIOD = 300  # 5分
    
    # Step Functions設定
    STEP_FUNCTIONS_TIMEOUT_MINUTES = 5
    
    # セキュリティ設定
    ALLOWED_ORIGINS = ["http://localhost:8100"]  # 開発用
    
    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """設定を辞書形式で取得"""
        return {
            "app": {
                "name": cls.APP_NAME,
                "description": cls.APP_DESCRIPTION,
            },
            "lambda": {
                "runtime": cls.LAMBDA_RUNTIME,
                "timeout": cls.LAMBDA_TIMEOUT_SECONDS,
                "memory_size": cls.LAMBDA_MEMORY_SIZE,
            },
            "bedrock": {
                "model_id": cls.BEDROCK_MODEL_ID,
                "max_tokens": cls.BEDROCK_MAX_TOKENS,
                "temperature": cls.BEDROCK_TEMPERATURE,
            },
            "dynamodb": {
                "billing_mode": cls.DYNAMODB_BILLING_MODE,
                "removal_policy": cls.DYNAMODB_REMOVAL_POLICY,
            },
            "api_gateway": {
                "throttle": {
                    "rate_limit": cls.API_GATEWAY_THROTTLE_RATE_LIMIT,
                    "burst_limit": cls.API_GATEWAY_THROTTLE_BURST_LIMIT,
                },
                "cors": {
                    "allowed_origins": cls.ALLOWED_ORIGINS,
                },
            },
            "websocket": {
                "route_selection_expression": cls.WEBSOCKET_ROUTE_SELECTION_EXPRESSION,
            },
            "cognito": {
                "password_policy": cls.COGNITO_PASSWORD_POLICY,
            },
            "monitoring": {
                "log_retention_days": cls.LOG_RETENTION_DAYS,
                "alarm": {
                    "evaluation_periods": cls.ALARM_EVALUATION_PERIODS,
                    "threshold_period": cls.ALARM_THRESHOLD_PERIOD,
                },
            },
            "step_functions": {
                "timeout_minutes": cls.STEP_FUNCTIONS_TIMEOUT_MINUTES,
            },
        }
    
    @classmethod
    def get_tags(cls) -> Dict[str, str]:
        """共通タグを取得"""
        return {
            "Application": cls.APP_NAME,
            "ManagedBy": "CDK",
        }
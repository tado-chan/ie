from aws_cdk import (
    aws_apigatewayv2 as apigatewayv2,
    aws_apigatewayv2_integrations as integrations,
    aws_apigatewayv2_authorizers as authorizers,
    aws_cognito as cognito,
    aws_lambda as lambda_,
    aws_iam as iam,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class WebSocketConstruct(Construct):
    """WebSocket API Gateway構築用コンストラクト"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        user_pool: cognito.UserPool,
        websocket_handlers: dict,
        config: dict = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config or {}
        self.user_pool = user_pool
        self.websocket_handlers = websocket_handlers

        # WebSocket API作成
        self.websocket_api = self._create_websocket_api()

        # ルート設定
        self._setup_routes()

        # ステージ作成
        self._create_stage()

        # 接続管理用のテーブルへのアクセス権限を付与
        self._grant_connection_permissions()

    def _create_websocket_api(self) -> apigatewayv2.WebSocketApi:
        """WebSocket APIを作成"""
        return apigatewayv2.WebSocketApi(
            self,
            "WebSocketApi",
            api_name=f"houkokusou-chatbot-ws-{self.env_name}",
            description="報連相チャットボット WebSocket API",
            connect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=integrations.WebSocketLambdaIntegration(
                    "ConnectIntegration",
                    self.websocket_handlers["connect"]
                ),
                # Cognitoトークンによる認証を追加する場合はここでAuthorizerを設定
            ),
            disconnect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=integrations.WebSocketLambdaIntegration(
                    "DisconnectIntegration",
                    self.websocket_handlers["disconnect"]
                )
            ),
            default_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=integrations.WebSocketLambdaIntegration(
                    "DefaultIntegration",
                    self.websocket_handlers["message"]
                )
            ),
        )

    def _setup_routes(self):
        """カスタムルートの設定"""
        # sendmessageルート（クライアントからのメッセージ送信）
        apigatewayv2.WebSocketRoute(
            self,
            "SendMessageRoute",
            web_socket_api=self.websocket_api,
            route_key="sendmessage",
            integration=integrations.WebSocketLambdaIntegration(
                "SendMessageIntegration",
                self.websocket_handlers["message"]
            ),
        )

        # statusルート（処理ステータスの確認）
        if "status" in self.websocket_handlers:
            apigatewayv2.WebSocketRoute(
                self,
                "StatusRoute",
                web_socket_api=self.websocket_api,
                route_key="status",
                integration=integrations.WebSocketLambdaIntegration(
                    "StatusIntegration",
                    self.websocket_handlers["status"]
                ),
            )

    def _create_stage(self):
        """WebSocket APIのステージを作成"""
        self.stage = apigatewayv2.WebSocketStage(
            self,
            "WebSocketStage",
            web_socket_api=self.websocket_api,
            stage_name=self.env_name,
            auto_deploy=True,
        )

    def _grant_connection_permissions(self):
        """Lambda関数にWebSocket API管理権限を付与"""
        # 各ハンドラーにWebSocket管理権限を付与
        for handler in self.websocket_handlers.values():
            self.websocket_api.grant_manage_connections(handler)

    def get_websocket_url(self) -> str:
        """WebSocket URLを取得"""
        return f"{self.websocket_api.api_endpoint}/{self.stage.stage_name}"

    def grant_manage_connections(self, lambda_function: lambda_.Function):
        """指定されたLambda関数にWebSocket接続管理権限を付与"""
        self.websocket_api.grant_manage_connections(lambda_function)
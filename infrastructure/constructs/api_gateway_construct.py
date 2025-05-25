from aws_cdk import (
    aws_apigateway as apigateway,
    aws_lambda as lambda_,
    aws_cognito as cognito,
    aws_iam as iam,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class ApiGatewayConstruct(Construct):
    """API Gateway構築用コンストラクト"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        user_pool: cognito.UserPool,
        input_handler_function: lambda_.Function,
        config: dict = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config or {}
        self.user_pool = user_pool
        self.input_handler_function = input_handler_function

        # REST API作成
        self.rest_api = self._create_rest_api()

        # Cognitoオーソライザー作成
        self.authorizer = self._create_authorizer()

        # APIリソースとメソッド設定
        self._setup_api_resources()

    def _create_rest_api(self) -> apigateway.RestApi:
        """REST APIを作成"""
        return apigateway.RestApi(
            self,
            "RestApi",
            rest_api_name=f"houkokusou-chatbot-{self.env_name}",
            description="報連相チャットボット REST API",
            deploy_options=apigateway.StageOptions(
                stage_name=self.env_name,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
                tracing_enabled=True,
                throttling_rate_limit=self.config.get("throttle", {}).get("rate_limit", 100),
                throttling_burst_limit=self.config.get("throttle", {}).get("burst_limit", 200),
            ),
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=self.config.get("cors", {}).get("allowed_origins", ["*"]),
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent",
                ],
                allow_credentials=True,
            ),
            endpoint_types=[apigateway.EndpointType.REGIONAL],
        )

    def _create_authorizer(self) -> apigateway.CognitoUserPoolsAuthorizer:
        """Cognitoオーソライザーを作成"""
        return apigateway.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name=f"houkokusou-chatbot-{self.env_name}-authorizer",
            identity_source="method.request.header.Authorization",
        )

    def _setup_api_resources(self):
        """APIリソースとメソッドを設定"""
        
        # /api/v1 ベースパス
        api_v1 = self.rest_api.root.add_resource("api").add_resource("v1")

        # /api/v1/chat リソース
        chat_resource = api_v1.add_resource("chat")

        # POST /api/v1/chat - チャットメッセージ送信
        chat_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(
                self.input_handler_function,
                proxy=True,
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    ),
                    apigateway.IntegrationResponse(
                        status_code="202",
                        selection_pattern="202",
                        response_parameters={
                            "method.response.header.Access-Control-Allow-Origin": "'*'",
                        },
                    ),
                ],
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                ),
                apigateway.MethodResponse(
                    status_code="202",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                ),
            ],
        )

        # /api/v1/chat/{conversationId} リソース
        chat_conversation_resource = chat_resource.add_resource("{conversationId}")

        # GET /api/v1/chat/{conversationId} - 会話履歴取得
        chat_conversation_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(
                self.input_handler_function,
                proxy=True,
            ),
            authorizer=self.authorizer,
            authorization_type=apigateway.AuthorizationType.COGNITO,
        )

        # /api/v1/health - ヘルスチェック（認証不要）
        health_resource = api_v1.add_resource("health")
        health_resource.add_method(
            "GET",
            apigateway.MockIntegration(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "healthy", "service": "houkokusou-chatbot"}'
                        },
                    )
                ],
                request_templates={
                    "application/json": '{"statusCode": 200}'
                },
            ),
            method_responses=[
                apigateway.MethodResponse(status_code="200")
            ],
        )

        # API使用量プランの設定（オプション）
        if self.config.get("enable_usage_plan", False):
            self._create_usage_plan()

    def _create_usage_plan(self):
        """API使用量プランを作成"""
        # APIキーの作成
        api_key = apigateway.ApiKey(
            self,
            "ApiKey",
            api_key_name=f"houkokusou-chatbot-{self.env_name}-key",
            description="API key for houkokusou chatbot",
        )

        # 使用量プランの作成
        usage_plan = apigateway.UsagePlan(
            self,
            "UsagePlan",
            name=f"houkokusou-chatbot-{self.env_name}-plan",
            description="Usage plan for houkokusou chatbot",
            api_stages=[
                apigateway.UsagePlanPerApiStage(
                    api=self.rest_api,
                    stage=self.rest_api.deployment_stage,
                )
            ],
            throttle=apigateway.ThrottleSettings(
                rate_limit=1000,
                burst_limit=2000,
            ),
            quota=apigateway.QuotaSettings(
                limit=10000,
                period=apigateway.Period.DAY,
            ),
        )

        # APIキーを使用量プランに関連付け
        usage_plan.add_api_key(api_key)
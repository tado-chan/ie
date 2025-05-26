from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_dynamodb as dynamodb,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
import os


class LambdaConstruct(Construct):
    """Lambda関数構築用コンストラクト"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        user_pool: cognito.UserPool,
        tables: dict,
        config: dict = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config or {}
        self.user_pool = user_pool
        self.tables = tables

        # Lambda Layer作成
        self.common_layer = self._create_common_layer()

        # Lambda関数作成
        self._create_lambda_functions()

    def _create_common_layer(self) -> lambda_.LayerVersion:
        """共通Lambda Layerを作成"""
        return lambda_.LayerVersion(
            self,
            "CommonLayer",
            code=lambda_.Code.from_asset("src/lambda/layers/common"),
            compatible_runtimes=[lambda_.Runtime.PYTHON_3_11],
            description="共通ライブラリとユーティリティ",
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_lambda_functions(self):
        """各Lambda関数を作成"""
        # 共通の環境変数
        common_env = {
            "ENVIRONMENT": self.env_name,
            "LOG_LEVEL": self.config.get("environment", {}).get("LOG_LEVEL", "INFO"),
            "POWERTOOLS_SERVICE_NAME": "houkokusou-chatbot",
            "POWERTOOLS_METRICS_NAMESPACE": "HoukokusouChatbot",
        }

        # Input Handler Lambda
        self.input_handler_function = self._create_function(
            "InputHandler",
            "src/lambda/api/input_handler",
            "Input Handler Lambda",
            {
                **common_env,
                "CONVERSATION_TABLE_NAME": self.tables["conversations"].table_name,
                "STATE_MACHINE_ARN": "",  # 後でStep Functionsから設定
            }
        )

        # ★ 新規追加: Status Handler Lambda
        self.status_handler_function = self._create_function(
            "StatusHandler",
            "src/lambda/api/status_handler",
            "Status Handler Lambda - Step Functions結果取得",
            {
                **common_env,
                "CONVERSATION_TABLE_NAME": self.tables["conversations"].table_name,
                "STATE_MACHINE_ARN": "",  # 後でStep Functionsから設定
            }
        )

        # WebSocket Handlers
        self.websocket_handlers = {
            "connect": self._create_function(
                "WebSocketConnect",
                "src/lambda/api/websocket_handler",
                "WebSocket Connect Handler",
                {
                    **common_env,
                    "HANDLER": "connect",
                    "CONNECTIONS_TABLE": self.tables["conversations"].table_name,
                },
                handler="connect.lambda_handler"
            ),
            "disconnect": self._create_function(
                "WebSocketDisconnect",
                "src/lambda/api/websocket_handler",
                "WebSocket Disconnect Handler",
                {
                    **common_env,
                    "HANDLER": "disconnect",
                    "CONNECTIONS_TABLE": self.tables["conversations"].table_name,
                },
                handler="disconnect.lambda_handler"
            ),
            "message": self._create_function(
                "WebSocketMessage",
                "src/lambda/api/websocket_handler",
                "WebSocket Message Handler",
                {
                    **common_env,
                    "HANDLER": "message",
                    "CONVERSATIONS_TABLE": self.tables["conversations"].table_name,
                },
                handler="message.lambda_handler"
            ),
        }

        # Auth Handler Lambda
        self.auth_handler_function = self._create_function(
            "AuthHandler",
            "src/lambda/api/auth_handler",
            "Authentication Handler Lambda",
            {
                **common_env,
                "USER_POOL_ID": self.user_pool.user_pool_id,
            }
        )

        # Bedrock Analyzer Lambda
        self.bedrock_analyzer_function = self._create_function(
            "BedrockAnalyzer",
            "src/lambda/processors/bedrock_analyzer",
            "Bedrock Analysis Lambda",
            {
                **common_env,
                "BEDROCK_MODEL_ID": self.config.get("bedrock", {}).get("model_id", "anthropic.claude-3-sonnet-20240229-v1:0"),
                "CONVERSATIONS_TABLE": self.tables["conversations"].table_name,
            },
            timeout=Duration.seconds(60),
            memory_size=1024,
        )

        # Bedrock権限を追加
        self.bedrock_analyzer_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )

        # Organization Matcher Lambda
        self.organization_matcher_function = self._create_function(
            "OrganizationMatcher",
            "src/lambda/processors/organization_matcher",
            "Organization Matching Lambda",
            {
                **common_env,
                "ORGANIZATIONS_TABLE": self.tables["organizations"].table_name,
                "SUGGESTIONS_TABLE": self.tables["suggestions"].table_name,
            }
        )

        # Notification Sender Lambda
        self.notification_sender_function = self._create_function(
            "NotificationSender",
            "src/lambda/processors/notification_sender",
            "Notification Sender Lambda",
            {
                **common_env,
                "CONVERSATIONS_TABLE": self.tables["conversations"].table_name,
            }
        )

        # Organization Manager Lambda (Admin)
        self.organization_manager_function = self._create_function(
            "OrganizationManager",
            "src/lambda/admin/organization_manager",
            "Organization Manager Lambda",
            {
                **common_env,
                "ORGANIZATIONS_TABLE": self.tables["organizations"].table_name,
            }
        )

        # ★ Step Functions読み取り権限を追加
        step_functions_policy = iam.PolicyStatement(
            actions=[
                "states:DescribeExecution",
                "states:GetExecutionHistory",
            ],
            resources=["*"],  # 具体的なARNは後で設定
        )
        
        self.status_handler_function.add_to_role_policy(step_functions_policy)
        self.input_handler_function.add_to_role_policy(
            iam.PolicyStatement(
                actions=["states:StartExecution"],
                resources=["*"],
            )
        )

        # DynamoDBアクセス権限を付与
        for table in self.tables.values():
            table.grant_read_write_data(self.input_handler_function)
            table.grant_read_write_data(self.status_handler_function)  # ★ 追加
            table.grant_read_write_data(self.bedrock_analyzer_function)
            table.grant_read_write_data(self.organization_matcher_function)
            table.grant_read_write_data(self.notification_sender_function)
            table.grant_read_write_data(self.organization_manager_function)
            
            # WebSocketハンドラーにも権限付与
            for handler in self.websocket_handlers.values():
                table.grant_read_write_data(handler)

    def _create_function(
        self,
        function_name: str,
        code_path: str,
        description: str,
        environment: dict,
        handler: str = "lambda_function.lambda_handler",
        timeout: Duration = None,
        memory_size: int = None,
    ) -> lambda_.Function:
        """Lambda関数を作成"""
        return lambda_.Function(
            self,
            function_name,
            function_name=f"houkokusou-chatbot-{self.env_name}-{function_name}",
            description=description,
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler=handler,
            code=lambda_.Code.from_asset(code_path),
            environment=environment,
            layers=[self.common_layer],
            timeout=timeout or Duration.seconds(30),
            memory_size=memory_size or 512,
            tracing=lambda_.Tracing.ACTIVE,
            retry_attempts=2,
        )

    def update_step_functions_arn(self, state_machine_arn: str):
        """Step FunctionsのARNを環境変数に設定"""
        self.input_handler_function.add_environment("STATE_MACHINE_ARN", state_machine_arn)
        self.status_handler_function.add_environment("STATE_MACHINE_ARN", state_machine_arn)  # ★ 追加
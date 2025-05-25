from aws_cdk import (
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_lambda as lambda_,
    aws_dynamodb as dynamodb,
    aws_apigatewayv2 as apigatewayv2,
    aws_logs as logs,
    Duration,
    RemovalPolicy,
)
from constructs import Construct
import json


class StepFunctionsConstruct(Construct):
    """Step Functions構築用コンストラクト"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        lambda_functions: dict,
        tables: dict,
        websocket_api: apigatewayv2.WebSocketApi,
        config: dict = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config or {}
        self.lambda_functions = lambda_functions
        self.tables = tables
        self.websocket_api = websocket_api

        # CloudWatch Logsグループ作成
        self.log_group = self._create_log_group()

        # ステートマシン作成
        self.state_machine = self._create_state_machine()

    def _create_log_group(self) -> logs.LogGroup:
        """CloudWatch Logsグループを作成"""
        return logs.LogGroup(
            self,
            "StateMachineLogGroup",
            log_group_name=f"/aws/stepfunctions/houkokusou-chatbot-{self.env_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY,
        )

    def _create_state_machine(self) -> sfn.StateMachine:
        """ステートマシンを作成"""
        # 初期化タスク
        initialize_task = tasks.DynamoUpdateItem(
            self,
            "InitializeConversation",
            table=self.tables["conversations"],
            key={
                "conversationId": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.conversationId")
                ),
            },
            update_expression="SET #status = :status, #timestamp = :timestamp",
            expression_attribute_names={
                "#status": "status",
                "#timestamp": "timestamp",
            },
            expression_attribute_values={
                ":status": tasks.DynamoAttributeValue.from_string("processing"),
                ":timestamp": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$$.State.EnteredTime")
                ),
            },
            result_path="$.initializeResult",
        )

        # Bedrock分析タスク
        bedrock_task = tasks.LambdaInvoke(
            self,
            "AnalyzeWithBedrock",
            lambda_function=self.lambda_functions["bedrock_analyzer"],
            payload=sfn.TaskInput.from_object({
                "conversationId": sfn.JsonPath.string_at("$.conversationId"),
                "message": sfn.JsonPath.string_at("$.message"),
                "context": sfn.JsonPath.object_at("$.context"),
            }),
            result_path="$.bedrockResult",
            retry_on_service_exceptions=True,
            retry=sfn.Retry(
                errors=["States.TaskFailed"],
                interval=Duration.seconds(2),
                max_attempts=3,
                backoff_rate=2,
            ),
        )

        # 組織マッチングタスク
        organization_task = tasks.LambdaInvoke(
            self,
            "MatchOrganization",
            lambda_function=self.lambda_functions["organization_matcher"],
            payload=sfn.TaskInput.from_object({
                "conversationId": sfn.JsonPath.string_at("$.conversationId"),
                "analysis": sfn.JsonPath.object_at("$.bedrockResult.Payload"),
                "userInfo": sfn.JsonPath.object_at("$.userInfo"),
            }),
            result_path="$.organizationResult",
        )

        # 結果保存とWebSocket通知の並列実行
        save_results = tasks.DynamoUpdateItem(
            self,
            "SaveResults",
            table=self.tables["suggestions"],
            key={
                "conversationId": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.conversationId")
                ),
            },
            update_expression="SET #suggestion = :suggestion, #status = :status",
            expression_attribute_names={
                "#suggestion": "suggestion",
                "#status": "status",
            },
            expression_attribute_values={
                ":suggestion": tasks.DynamoAttributeValue.from_json(
                    sfn.JsonPath.object_at("$.organizationResult.Payload")
                ),
                ":status": tasks.DynamoAttributeValue.from_string("completed"),
            },
            result_path="$.saveResult",
        )

        notify_client = tasks.LambdaInvoke(
            self,
            "NotifyClient",
            lambda_function=self.lambda_functions["notification_sender"],
            payload=sfn.TaskInput.from_object({
                "connectionId": sfn.JsonPath.string_at("$.connectionId"),
                "conversationId": sfn.JsonPath.string_at("$.conversationId"),
                "suggestion": sfn.JsonPath.object_at("$.organizationResult.Payload"),
                "websocketEndpoint": self.websocket_api.api_endpoint,
            }),
            result_path="$.notifyResult",
        )

        # 並列実行
        parallel_tasks = sfn.Parallel(
            self,
            "SaveAndNotify",
            result_path="$.parallelResults",
        )
        parallel_tasks.branch(save_results)
        parallel_tasks.branch(notify_client)

        # エラーハンドリング
        error_handler = tasks.DynamoUpdateItem(
            self,
            "HandleError",
            table=self.tables["conversations"],
            key={
                "conversationId": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.conversationId")
                ),
            },
            update_expression="SET #status = :status, #error = :error",
            expression_attribute_names={
                "#status": "status",
                "#error": "error",
            },
            expression_attribute_values={
                ":status": tasks.DynamoAttributeValue.from_string("error"),
                ":error": tasks.DynamoAttributeValue.from_string(
                    sfn.JsonPath.string_at("$.error")
                ),
            },
        )

        # タスクチェーンの構築
        definition = (
            initialize_task
            .next(bedrock_task)
            .next(organization_task)
            .next(parallel_tasks)
            .add_catch(
                error_handler,
                errors=["States.ALL"],
                result_path="$.error",
            )
        )

        # ステートマシン作成
        return sfn.StateMachine(
            self,
            "ChatProcessorStateMachine",
            definition=definition,
            state_machine_name=f"houkokusou-chatbot-processor-{self.env_name}",
            logs=sfn.LogOptions(
                destination=self.log_group,
                level=sfn.LogLevel.ALL,
            ),
            tracing_enabled=True,
        )
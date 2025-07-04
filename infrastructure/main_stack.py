from aws_cdk import (
    Stack,
    CfnOutput,
    aws_lambda as lambda_,
    aws_apigateway as apigateway,
    aws_iam as iam,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    Duration,
)
from constructs import Construct


class HoukokusouChatbotStack(Stack):
    """報連相チャットボットのメインスタック（Bedrock対応版）"""
    
    def __init__(self, scope: Construct, construct_id: str, env_name: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # 1. Lambda関数の作成
        # Input Handler Lambda
        self.input_handler = lambda_.Function(
            self,
            "InputHandler",
            function_name=f"houkokusou-chatbot-{env_name}-input-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("src/lambda/api/input_handler"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "ENVIRONMENT": env_name,
            }
        )
        
        # ★ Status Handler Lambda
        self.status_handler = lambda_.Function(
            self,
            "StatusHandler",
            function_name=f"houkokusou-chatbot-{env_name}-status-handler",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("src/lambda/api/status_handler"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "ENVIRONMENT": env_name,
            }
        )
        
        # Bedrock Analyzer Lambda
        self.bedrock_analyzer = lambda_.Function(
            self,
            "BedrockAnalyzer",
            function_name=f"houkokusou-chatbot-{env_name}-bedrock-analyzer",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset("src/lambda/processors/bedrock_analyzer"),
            timeout=Duration.seconds(60),
            memory_size=512,
            environment={
                "ENVIRONMENT": env_name,
            }
        )
        
        # Bedrock権限を追加
        self.bedrock_analyzer.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream",
                ],
                resources=["*"],
            )
        )
        
        # 2. Step Functionsの作成
        # Bedrock分析タスク
        analyze_task = tasks.LambdaInvoke(
            self,
            "AnalyzeWithBedrock",
            lambda_function=self.bedrock_analyzer,
            output_path="$.Payload",
        )
        
        # ステートマシンの定義
        definition = analyze_task
        
        # ステートマシンの作成
        self.state_machine = sfn.StateMachine(
            self,
            "ChatProcessorStateMachine",
            definition=definition,
            state_machine_name=f"houkokusou-chatbot-{env_name}-processor",
        )
        
        # ★ Step Functions権限を付与
        # Input HandlerにStep Functions実行権限を付与
        self.state_machine.grant_start_execution(self.input_handler)
        
        # Status HandlerにStep Functions読み取り権限を付与
        self.status_handler.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "states:DescribeExecution",
                    "states:GetExecutionHistory",
                    "sts:GetCallerIdentity",
                ],
                resources=["*"],
            )
        )
        
        # Input Handlerの環境変数にState Machine ARNを追加
        self.input_handler.add_environment("STATE_MACHINE_ARN", self.state_machine.state_machine_arn)
        
        # ★ Status Handlerの環境変数にState Machine ARNを追加
        self.status_handler.add_environment("STATE_MACHINE_ARN", self.state_machine.state_machine_arn)
        
        # 3. API Gatewayの作成
        self.api = apigateway.RestApi(
            self,
            "Api",
            rest_api_name=f"houkokusou-chatbot-{env_name}",
            description="報連相チャットボット API",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS"],
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key", "X-Amz-Security-Token"],
            ),
        )
        
        # /api/v1 リソース作成
        api_v1 = self.api.root.add_resource("api").add_resource("v1")
        chat_resource = api_v1.add_resource("chat")
        
        # POST /api/v1/chat
        chat_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self.input_handler),
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
        
        # ★ /api/v1/chat/{conversationId}/status
        conversation_resource = chat_resource.add_resource("{conversationId}")
        status_resource = conversation_resource.add_resource("status")
        
        status_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self.status_handler),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        "method.response.header.Access-Control-Allow-Origin": True,
                    },
                ),
            ],
        )
        
        # ヘルスチェックエンドポイント
        health_resource = api_v1.add_resource("health")
        health_resource.add_method(
            "GET",
            apigateway.MockIntegration(
                integration_responses=[
                    apigateway.IntegrationResponse(
                        status_code="200",
                        response_templates={
                            "application/json": '{"status": "healthy"}'
                        }
                    )
                ],
                request_templates={
                    "application/json": '{"statusCode": 200}'
                }
            ),
            method_responses=[
                apigateway.MethodResponse(status_code="200")
            ]
        )
        
        # 出力
        CfnOutput(
            self,
            "ApiUrl",
            value=self.api.url,
            description="API Gateway URL"
        )
        
        CfnOutput(
            self,
            "ApiEndpoint",
            value=f"{self.api.url}api/v1/chat",
            description="Chat API Endpoint"
        )
        
        CfnOutput(
            self,
            "StatusEndpoint",
            value=f"{self.api.url}api/v1/chat/{{conversationId}}/status",
            description="Status Check API Endpoint"
        )
        
        CfnOutput(
            self,
            "StateMachineArn",
            value=self.state_machine.state_machine_arn,
            description="Step Functions State Machine ARN"
        )
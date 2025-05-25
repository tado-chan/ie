from aws_cdk import (
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_lambda as lambda_,
    aws_stepfunctions as sfn,
    aws_apigateway as apigateway,
    Duration,
)
from constructs import Construct
from typing import List


class MonitoringConstruct(Construct):
    """CloudWatch監視構築用コンストラクト"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        lambda_functions: List[lambda_.Function],
        state_machine: sfn.StateMachine,
        api_gateway: apigateway.RestApi,
        config: dict = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config or {}
        self.lambda_functions = lambda_functions
        self.state_machine = state_machine
        self.api_gateway = api_gateway

        # SNSトピックの作成（アラーム通知用）
        self.alarm_topic = self._create_alarm_topic()

        # ダッシュボードの作成
        self.dashboard = self._create_dashboard()

        # アラームの作成
        self._create_alarms()

    def _create_alarm_topic(self) -> sns.Topic:
        """アラーム通知用のSNSトピックを作成"""
        return sns.Topic(
            self,
            "AlarmTopic",
            topic_name=f"houkokusou-chatbot-{self.env_name}-alarms",
            display_name="報連相チャットボット アラーム通知",
        )

    def _create_dashboard(self) -> cloudwatch.Dashboard:
        """CloudWatchダッシュボードを作成"""
        dashboard = cloudwatch.Dashboard(
            self,
            "Dashboard",
            dashboard_name=f"houkokusou-chatbot-{self.env_name}",
            default_interval=Duration.hours(1),
        )

        # Lambda関数のメトリクス
        for func in self.lambda_functions:
            dashboard.add_widgets(
                cloudwatch.GraphWidget(
                    title=f"{func.function_name} - Invocations & Errors",
                    left=[
                        func.metric_invocations(
                            statistic=cloudwatch.Stats.SUM,
                            period=Duration.minutes(5),
                        ),
                    ],
                    right=[
                        func.metric_errors(
                            statistic=cloudwatch.Stats.SUM,
                            period=Duration.minutes(5),
                        ),
                    ],
                    width=12,
                ),
                cloudwatch.GraphWidget(
                    title=f"{func.function_name} - Duration",
                    left=[
                        func.metric_duration(
                            statistic=cloudwatch.Stats.AVERAGE,
                            period=Duration.minutes(5),
                        ),
                    ],
                    width=12,
                ),
            )

        # API Gatewayのメトリクス
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="API Gateway - Request Count",
                left=[
                    cloudwatch.Metric(
                        metric_name="Count",
                        namespace="AWS/ApiGateway",
                        dimensions_map={
                            "ApiName": self.api_gateway.rest_api_name,
                        },
                        statistic=cloudwatch.Stats.SUM,
                        period=Duration.minutes(5),
                    ),
                ],
                width=12,
            ),
            cloudwatch.GraphWidget(
                title="API Gateway - Latency",
                left=[
                    cloudwatch.Metric(
                        metric_name="Latency",
                        namespace="AWS/ApiGateway",
                        dimensions_map={
                            "ApiName": self.api_gateway.rest_api_name,
                        },
                        statistic=cloudwatch.Stats.AVERAGE,
                        period=Duration.minutes(5),
                    ),
                ],
                width=12,
            ),
        )

        # Step Functionsのメトリクス
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Step Functions - Executions",
                left=[
                    self.state_machine.metric_started(
                        statistic=cloudwatch.Stats.SUM,
                        period=Duration.minutes(5),
                    ),
                    self.state_machine.metric_succeeded(
                        statistic=cloudwatch.Stats.SUM,
                        period=Duration.minutes(5),
                    ),
                    self.state_machine.metric_failed(
                        statistic=cloudwatch.Stats.SUM,
                        period=Duration.minutes(5),
                    ),
                ],
                width=24,
            ),
        )

        return dashboard

    def _create_alarms(self):
        """CloudWatchアラームを作成"""
        
        # Lambda関数のエラーアラーム
        for func in self.lambda_functions:
            error_alarm = cloudwatch.Alarm(
                self,
                f"{func.function_name}ErrorAlarm",
                alarm_name=f"{func.function_name}-errors",
                alarm_description=f"Error rate alarm for {func.function_name}",
                metric=func.metric_errors(
                    statistic=cloudwatch.Stats.SUM,
                    period=Duration.minutes(5),
                ),
                threshold=5,
                evaluation_periods=1,
                datapoints_to_alarm=1,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            error_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))

            # 高レイテンシアラーム
            latency_alarm = cloudwatch.Alarm(
                self,
                f"{func.function_name}LatencyAlarm",
                alarm_name=f"{func.function_name}-high-latency",
                alarm_description=f"High latency alarm for {func.function_name}",
                metric=func.metric_duration(
                    statistic=cloudwatch.Stats.AVERAGE,
                    period=Duration.minutes(5),
                ),
                threshold=3000,  # 3秒
                evaluation_periods=2,
                datapoints_to_alarm=2,
                treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            )
            latency_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))

        # API Gateway 4XXエラーアラーム
        api_4xx_alarm = cloudwatch.Alarm(
            self,
            "ApiGateway4xxAlarm",
            alarm_name=f"houkokusou-chatbot-{self.env_name}-api-4xx",
            alarm_description="High 4XX error rate",
            metric=cloudwatch.Metric(
                metric_name="4XXError",
                namespace="AWS/ApiGateway",
                dimensions_map={
                    "ApiName": self.api_gateway.rest_api_name,
                },
                statistic=cloudwatch.Stats.AVERAGE,
                period=Duration.minutes(5),
            ),
            threshold=0.1,  # 10%
            evaluation_periods=2,
            datapoints_to_alarm=2,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        api_4xx_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))

        # Step Functions失敗アラーム
        sfn_failure_alarm = cloudwatch.Alarm(
            self,
            "StepFunctionsFailureAlarm",
            alarm_name=f"houkokusou-chatbot-{self.env_name}-sfn-failures",
            alarm_description="Step Functions execution failures",
            metric=self.state_machine.metric_failed(
                statistic=cloudwatch.Stats.SUM,
                period=Duration.minutes(5),
            ),
            threshold=3,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        sfn_failure_alarm.add_alarm_action(cw_actions.SnsAction(self.alarm_topic))
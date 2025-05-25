from aws_cdk import (
    aws_dynamodb as dynamodb,
    RemovalPolicy,
    Duration,
)
from constructs import Construct


class DynamoDBConstruct(Construct):
    """DynamoDB構築用コンストラクト"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        env_name: str,
        config: dict = None,
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.env_name = env_name
        self.config = config or {}

        # 各テーブルを作成
        self._create_tables()

    def _create_tables(self):
        """DynamoDBテーブルを作成"""
        
        # 会話テーブル
        self.conversations_table = dynamodb.Table(
            self,
            "ConversationsTable",
            table_name=f"houkokusou-chatbot-{self.env_name}-conversations",
            partition_key=dynamodb.Attribute(
                name="conversationId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True if self.env_name == "prod" else False,
            time_to_live_attribute="ttl",
            stream=dynamodb.StreamViewType.NEW_AND_OLD_IMAGES,
        )

        # GSI: userId でクエリできるように
        self.conversations_table.add_global_secondary_index(
            index_name="userId-timestamp-index",
            partition_key=dynamodb.Attribute(
                name="userId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # 組織構造テーブル
        self.organizations_table = dynamodb.Table(
            self,
            "OrganizationsTable",
            table_name=f"houkokusou-chatbot-{self.env_name}-organizations",
            partition_key=dynamodb.Attribute(
                name="organizationId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="departmentId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True if self.env_name == "prod" else False,
        )

        # GSI: 部署名で検索
        self.organizations_table.add_global_secondary_index(
            index_name="departmentName-index",
            partition_key=dynamodb.Attribute(
                name="departmentName",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # 提案履歴テーブル
        self.suggestions_table = dynamodb.Table(
            self,
            "SuggestionsTable",
            table_name=f"houkokusou-chatbot-{self.env_name}-suggestions",
            partition_key=dynamodb.Attribute(
                name="conversationId",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="suggestionId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            point_in_time_recovery=True if self.env_name == "prod" else False,
            time_to_live_attribute="ttl",
        )

        # GSI: カテゴリ別の提案を検索
        self.suggestions_table.add_global_secondary_index(
            index_name="category-timestamp-index",
            partition_key=dynamodb.Attribute(
                name="category",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # WebSocket接続管理テーブル（オプション）
        if self.config.get("enable_websocket_connections_table", True):
            self.connections_table = dynamodb.Table(
                self,
                "ConnectionsTable",
                table_name=f"houkokusou-chatbot-{self.env_name}-connections",
                partition_key=dynamodb.Attribute(
                    name="connectionId",
                    type=dynamodb.AttributeType.STRING
                ),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=RemovalPolicy.DESTROY,
                time_to_live_attribute="ttl",
            )

            # GSI: userId で接続を検索
            self.connections_table.add_global_secondary_index(
                index_name="userId-index",
                partition_key=dynamodb.Attribute(
                    name="userId",
                    type=dynamodb.AttributeType.STRING
                ),
                projection_type=dynamodb.ProjectionType.ALL,
            )
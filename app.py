#!/usr/bin/env python3
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import aws_cdk as cdk
from infrastructure.main_stack import HoukokusouChatbotStack
from infrastructure.config.dev import DevConfig
from infrastructure.config.staging import StagingConfig
from infrastructure.config.prod import ProdConfig

app = cdk.App()

# 環境名を取得（デフォルトはdev）
env_name = app.node.try_get_context("env") or "dev"

# 環境に応じた設定を選択
config_map = {
    "dev": DevConfig,
    "staging": StagingConfig,
    "prod": ProdConfig,
}

config_class = config_map.get(env_name, DevConfig)
config = config_class.get_config()

# AWS環境の設定
# 環境変数から取得、なければデフォルト値を使用
aws_account = os.environ.get("CDK_DEFAULT_ACCOUNT", os.environ.get("AWS_ACCOUNT_ID"))
aws_region = os.environ.get("CDK_DEFAULT_REGION", os.environ.get("AWS_REGION", "ap-northeast-1"))

if not aws_account:
    print("Warning: AWS_ACCOUNT_ID is not set. Using current AWS credentials.")
    # AWS CLIの設定から取得を試みる
    import boto3
    try:
        sts = boto3.client("sts")
        aws_account = sts.get_caller_identity()["Account"]
    except Exception as e:
        print(f"Error getting AWS account: {e}")
        aws_account = "123456789012"  # ダミー値

# スタックの作成
stack = HoukokusouChatbotStack(
    app,
    f"HoukokusouChatbotStack-{env_name}",
    env=cdk.Environment(
        account=aws_account,
        region=aws_region,
    ),
    env_name=env_name,
    config=config,
    description=f"Houkokusou Chatbot Stack for {env_name} environment",
)

# タグの追加
cdk.Tags.of(app).add("Project", "HoukokusouChatbot")
cdk.Tags.of(app).add("Environment", env_name)
cdk.Tags.of(app).add("ManagedBy", "CDK")

app.synth()
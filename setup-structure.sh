#!/bin/bash
# プロジェクト構造セットアップスクリプト

echo "Setting up project structure..."

# ディレクトリ作成
directories=(
    "infrastructure/constructs"
    "infrastructure/config"
    "src/lambda/layers/common/python/models"
    "src/lambda/layers/common/python/utils"
    "src/lambda/api/input_handler"
    "src/lambda/api/websocket_handler"
    "src/lambda/api/auth_handler"
    "src/lambda/processors/bedrock_analyzer/prompts"
    "src/lambda/processors/organization_matcher"
    "src/lambda/processors/notification_sender"
    "src/lambda/admin/organization_manager"
    "state_machines/definitions"
    "data"
    "tests/unit/lambda"
    "tests/unit/infrastructure"
    "tests/integration/api"
    "tests/e2e/scenarios"
    "scripts/setup"
    "scripts/deploy"
    "scripts/utils"
    "monitoring/dashboards"
    "monitoring/alarms"
    "monitoring/queries"
    "docs/architecture"
    "docs/api"
    "docs/deployment"
    "docs/development"
)

for dir in "${directories[@]}"; do
    mkdir -p "$dir"
    echo "Created: $dir"
done

# __init__.pyファイルを作成
init_files=(
    "infrastructure/__init__.py"
    "infrastructure/constructs/__init__.py"
    "infrastructure/config/__init__.py"
    "src/lambda/layers/common/python/__init__.py"
    "src/lambda/layers/common/python/models/__init__.py"
    "src/lambda/layers/common/python/utils/__init__.py"
    "src/lambda/processors/bedrock_analyzer/prompts/__init__.py"
    "state_machines/__init__.py"
)

for file in "${init_files[@]}"; do
    touch "$file"
    echo "Created: $file"
done

# プロンプトテンプレートファイルを作成
cat > src/lambda/processors/bedrock_analyzer/prompts/templates.py << 'EOF'
"""Bedrock分析用プロンプトテンプレート"""

ANALYSIS_PROMPT_TEMPLATE = """あなたは社内の報連相（報告・連絡・相談）をサポートするアシスタントです。
ユーザーからの相談内容を分析し、適切な報告先と伝え方を提案してください。

■ ユーザーからの相談:
{message}

{history}

{context}

以下の観点で分析し、JSON形式で回答してください：

1. カテゴリ分類（技術的な問題、業務相談、人事・組織、その他）
2. 緊急度（高、中、低）
3. 推奨される報告先（部署、役職）
4. 報告理由
5. 推奨されるメッセージ例
6. キーワード（関連する重要な単語）

回答形式:
{{
    "category": "カテゴリ",
    "urgency": "緊急度",
    "recommended_recipients": [
        {{
            "department": "部署名",
            "role": "役職",
            "reason": "この人に報告すべき理由"
        }}
    ],
    "suggested_message": "報告メッセージの例",
    "keywords": ["キーワード1", "キーワード2"],
    "additional_notes": "追加のアドバイス"
}}
"""
EOF

# Lambda Layer の requirements.txt
cat > src/lambda/layers/common/requirements.txt << 'EOF'
boto3>=1.28.0
aws-lambda-powertools>=2.25.0
pydantic>=2.0.0
EOF

# 各Lambda関数の requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/api/input_handler/requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/api/websocket_handler/requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/api/auth_handler/requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/processors/bedrock_analyzer/requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/processors/organization_matcher/requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/processors/notification_sender/requirements.txt
echo "aws-lambda-powertools>=2.25.0" > src/lambda/admin/organization_manager/requirements.txt

# 設定ファイルのスタブを作成
echo "from .base import BaseConfig

class StagingConfig(BaseConfig):
    ENV_NAME = 'staging'" > infrastructure/config/staging.py

echo "from .base import BaseConfig

class ProdConfig(BaseConfig):
    ENV_NAME = 'prod'" > infrastructure/config/prod.py

echo "✅ Project structure setup complete!"
echo ""
echo "Next steps:"
echo "1. Run: pip install -r requirements.txt"
echo "2. Run: cdk synth --context env=dev"
echo "3. Run: cdk bootstrap --context env=dev"
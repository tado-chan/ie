import json
import os
from typing import Dict, Any, List

import boto3
from aws_lambda_powertools import Logger, Tracer, Metrics
from aws_lambda_powertools.metrics import MetricUnit
from aws_lambda_powertools.utilities.typing import LambdaContext

from prompts.templates import ANALYSIS_PROMPT_TEMPLATE

# Lambda Powertools
logger = Logger()
tracer = Tracer()
metrics = Metrics()

# AWS Clients
bedrock_runtime = boto3.client("bedrock-runtime")
dynamodb = boto3.resource("dynamodb")

# Environment variables
BEDROCK_MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "anthropic.claude-3-sonnet-20240229-v1:0")
CONVERSATIONS_TABLE = os.environ["CONVERSATIONS_TABLE"]

# DynamoDB table
conversations_table = dynamodb.Table(CONVERSATIONS_TABLE)


@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@metrics.log_metrics(capture_cold_start_metric=True)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """
    Bedrockを使用してユーザーの相談内容を分析
    
    Args:
        event: Step Functionsからのイベント
        context: Lambda実行コンテキスト
    
    Returns:
        分析結果
    """
    try:
        conversation_id = event["conversationId"]
        message = event["message"]
        context_info = event.get("context", {})
        
        # 会話履歴の取得
        conversation_history = get_conversation_history(conversation_id)
        
        # プロンプトの生成
        prompt = create_analysis_prompt(
            message=message,
            context_info=context_info,
            conversation_history=conversation_history
        )
        
        # Bedrockで分析
        analysis_result = analyze_with_bedrock(prompt)
        
        # 分析結果の構造化
        structured_result = structure_analysis_result(analysis_result)
        
        # 会話レコードの更新
        update_conversation_analysis(conversation_id, structured_result)
        
        # メトリクスの記録
        metrics.add_metric(name="BedrockAnalysisCompleted", unit=MetricUnit.Count, value=1)
        
        return structured_result
        
    except Exception as e:
        logger.error(f"Analysis error: {str(e)}", exc_info=True)
        metrics.add_metric(name="BedrockAnalysisError", unit=MetricUnit.Count, value=1)
        raise


@tracer.capture_method
def get_conversation_history(conversation_id: str) -> List[Dict[str, Any]]:
    """
    会話履歴を取得
    
    Args:
        conversation_id: 会話ID
    
    Returns:
        会話履歴のリスト
    """
    try:
        response = conversations_table.get_item(
            Key={"conversationId": conversation_id}
        )
        
        if "Item" in response:
            return response["Item"].get("history", [])
        return []
    except Exception as e:
        logger.warning(f"Failed to get conversation history: {str(e)}")
        return []


@tracer.capture_method
def create_analysis_prompt(
    message: str,
    context_info: Dict[str, Any],
    conversation_history: List[Dict[str, Any]]
) -> str:
    """
    分析用プロンプトを生成
    
    Args:
        message: ユーザーメッセージ
        context_info: コンテキスト情報
        conversation_history: 会話履歴
    
    Returns:
        プロンプト文字列
    """
    # 会話履歴を文字列に変換
    history_text = ""
    if conversation_history:
        history_text = "■ これまでの会話履歴:\n"
        for item in conversation_history[-5:]:  # 最新5件まで
            role = "ユーザー" if item["role"] == "user" else "アシスタント"
            history_text += f"{role}: {item['message']}\n"
    
    # コンテキスト情報を文字列に変換
    context_text = ""
    if context_info:
        context_text = "■ 追加情報:\n"
        if context_info.get("urgency"):
            context_text += f"緊急度: {context_info['urgency']}\n"
        if context_info.get("category"):
            context_text += f"カテゴリ: {context_info['category']}\n"
    
    return ANALYSIS_PROMPT_TEMPLATE.format(
        message=message,
        history=history_text,
        context=context_text
    )


@tracer.capture_method
def analyze_with_bedrock(prompt: str) -> str:
    """
    Bedrockを使用して分析を実行
    
    Args:
        prompt: プロンプト
    
    Returns:
        分析結果のテキスト
    """
    try:
        # Bedrockへのリクエスト
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1000,
                "temperature": 0.7,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            })
        )
        
        # レスポンスの解析
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]
        
    except Exception as e:
        logger.error(f"Bedrock invocation error: {str(e)}")
        raise


@tracer.capture_method
def structure_analysis_result(analysis_text: str) -> Dict[str, Any]:
    """
    分析結果を構造化
    
    Args:
        analysis_text: 分析結果のテキスト
    
    Returns:
        構造化された分析結果
    """
    try:
        # Bedrockの出力がJSON形式の場合はパース
        if analysis_text.strip().startswith("{"):
            return json.loads(analysis_text)
        
        # テキスト形式の場合は構造化
        return {
            "analysis": analysis_text,
            "category": extract_category(analysis_text),
            "urgency": extract_urgency(analysis_text),
            "suggested_actions": extract_suggested_actions(analysis_text),
            "keywords": extract_keywords(analysis_text)
        }
    except Exception as e:
        logger.warning(f"Failed to structure analysis: {str(e)}")
        return {
            "analysis": analysis_text,
            "category": "その他",
            "urgency": "通常",
            "suggested_actions": [],
            "keywords": []
        }


@tracer.capture_method
def extract_category(text: str) -> str:
    """カテゴリを抽出（簡易実装）"""
    categories = {
        "技術的な問題": ["エラー", "バグ", "不具合", "システム"],
        "業務相談": ["業務", "仕事", "タスク", "プロジェクト"],
        "人事・組織": ["人事", "組織", "部署", "異動"],
        "その他": []
    }
    
    for category, keywords in categories.items():
        if any(keyword in text for keyword in keywords):
            return category
    
    return "その他"


@tracer.capture_method
def extract_urgency(text: str) -> str:
    """緊急度を抽出（簡易実装）"""
    if any(word in text for word in ["緊急", "至急", "今すぐ", "大至急"]):
        return "高"
    elif any(word in text for word in ["なるべく早く", "早めに", "急ぎ"]):
        return "中"
    return "低"


@tracer.capture_method
def extract_suggested_actions(text: str) -> List[str]:
    """提案されたアクションを抽出（簡易実装）"""
    actions = []
    
    # 簡易的なパターンマッチング
    if "報告" in text:
        actions.append("上司への報告")
    if "相談" in text:
        actions.append("チームメンバーへの相談")
    if "確認" in text:
        actions.append("関係者への確認")
    
    return actions if actions else ["適切な担当者への連絡"]


@tracer.capture_method
def extract_keywords(text: str) -> List[str]:
    """キーワードを抽出（簡易実装）"""
    # 実際の実装では形態素解析などを使用
    return ["報告", "相談", "連絡"]


@tracer.capture_method
def update_conversation_analysis(conversation_id: str, analysis_result: Dict[str, Any]) -> None:
    """
    会話レコードに分析結果を更新
    
    Args:
        conversation_id: 会話ID
        analysis_result: 分析結果
    """
    conversations_table.update_item(
        Key={"conversationId": conversation_id},
        UpdateExpression="SET analysis = :analysis, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":analysis": analysis_result,
            ":updatedAt": datetime.utcnow().isoformat()
        }
    )
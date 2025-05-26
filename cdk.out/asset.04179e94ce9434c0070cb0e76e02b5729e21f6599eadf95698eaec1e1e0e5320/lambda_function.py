import json
import boto3
import os

# Bedrock Runtimeクライアント
bedrock_runtime = boto3.client('bedrock-runtime', region_name='ap-northeast-1')

def lambda_handler(event, context):
    """
    Bedrockを使用してユーザーの相談内容を分析
    """
    print(f"Event: {json.dumps(event)}")
    
    try:
        # Step Functionsから受け取るデータ
        message = event.get('message', '')
        conversation_id = event.get('conversationId', '')
        
        # プロンプトの作成
        prompt = f"""あなたは社内の報連相（報告・連絡・相談）をサポートするアシスタントです。
以下の相談内容を分析し、適切な報告先と伝え方を提案してください。

相談内容: {message}

以下の観点で分析してください：
1. この相談の種類は何か（例：人間関係、業務改善、スキル向上など）
2. 誰に相談すべきか（例：直属の上司、人事部、同僚など）
3. どのように伝えるべきか（具体的な言い方の例）

回答は日本語で、具体的かつ実用的なアドバイスをお願いします。"""

        # Bedrockへのリクエスト
        response = bedrock_runtime.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',  # 高速で安価なモデル
            contentType='application/json',
            accept='application/json',
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
        response_body = json.loads(response['body'].read())
        analysis_result = response_body['content'][0]['text']
        
        # 結果を構造化
        result = {
            "conversationId": conversation_id,
            "analysis": analysis_result,
            "category": "人間関係",  # 後で動的に判定
            "recommendedRecipient": "直属の上司",  # 後で動的に判定
            "timestamp": event.get('timestamp', '')
        }
        
        return result
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "error": str(e),
            "conversationId": conversation_id
        }

from aws_cdk import Stack
from constructs import Construct


class HoukokusouChatbotStack(Stack):
    """報連相チャットボットのメインスタック（最小構成）"""
    
    def __init__(self, scope: Construct, construct_id: str, env_name: str, config: dict, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # 一旦空のスタックで動作確認
        pass
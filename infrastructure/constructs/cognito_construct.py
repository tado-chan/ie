from aws_cdk import (
    aws_cognito as cognito,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class CognitoConstruct(Construct):
    """Cognito構築用コンストラクト"""

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

        # User Pool作成
        self.user_pool = self._create_user_pool()
        
        # User Pool Client作成
        self.user_pool_client = self._create_user_pool_client()
        
        # Identity Pool作成（オプション）
        if self.config.get("enable_identity_pool", False):
            self.identity_pool = self._create_identity_pool()

    def _create_user_pool(self) -> cognito.UserPool:
        """Cognito User Poolを作成"""
        password_policy = self.config.get("password_policy", {})
        
        return cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=f"houkokusou-chatbot-{self.env_name}",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(
                email=True,
                username=False,
            ),
            auto_verify=cognito.AutoVerifiedAttrs(
                email=True,
            ),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(
                    required=True,
                    mutable=True,
                ),
                fullname=cognito.StandardAttribute(
                    required=False,
                    mutable=True,
                ),
            ),
            custom_attributes={
                "department": cognito.StringAttribute(
                    min_len=1,
                    max_len=100,
                    mutable=True,
                ),
                "role": cognito.StringAttribute(
                    min_len=1,
                    max_len=100,
                    mutable=True,
                ),
                "employeeId": cognito.StringAttribute(
                    min_len=1,
                    max_len=50,
                    mutable=False,
                ),
            },
            password_policy=cognito.PasswordPolicy(
                min_length=password_policy.get("min_length", 8),
                require_lowercase=password_policy.get("require_lowercase", True),
                require_uppercase=password_policy.get("require_uppercase", True),
                require_digits=password_policy.get("require_digits", True),
                require_symbols=password_policy.get("require_symbols", True),
                temp_password_validity=Duration.days(7),
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY if self.env_name == "dev" else RemovalPolicy.RETAIN,
            email=cognito.UserPoolEmail.with_ses(
                from_email="noreply@houkokusou-chatbot.com",
                from_name="報連相チャットボット",
                reply_to="support@houkokusou-chatbot.com",
            ) if self.env_name == "prod" else None,
        )

    def _create_user_pool_client(self) -> cognito.UserPoolClient:
        """User Pool Clientを作成"""
        return self.user_pool.add_client(
            "WebClient",
            user_pool_client_name=f"houkokusou-chatbot-{self.env_name}-web",
            generate_secret=False,  # SPAクライアント用
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
                custom=True,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True,
                ),
                scopes=[
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.PROFILE,
                ],
                callback_urls=[
                    "http://localhost:8100/auth/callback",
                    f"https://app-{self.env_name}.houkokusou-chatbot.com/auth/callback",
                ],
                logout_urls=[
                    "http://localhost:8100/auth/logout",
                    f"https://app-{self.env_name}.houkokusou-chatbot.com/auth/logout",
                ],
            ) if self.config.get("enable_oauth", False) else None,
            prevent_user_existence_errors=True,
            enable_token_revocation=True,
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(30),
        )

    def _create_identity_pool(self) -> cognito.CfnIdentityPool:
        """Identity Poolを作成（オプション）"""
        return cognito.CfnIdentityPool(
            self,
            "IdentityPool",
            identity_pool_name=f"houkokusou_chatbot_{self.env_name}",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name,
                )
            ],
        )
"""
Cognito OAuth を使用して AgentCore Gateway を作成し、設定を保存するためのセットアップスクリプト。

引数（環境変数または以下を編集して指定）：
  GATEWAY_NAME   - ゲートウェイの名前（オプション。設定されておらず自動生成される）
  GATEWAY_REGION - AWSリージョン（デフォルト: us-west-2）
  GATEWAY_CONFIG - 出力JSONファイルのパス（デフォルト: gateway_config.json）
"""

from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient
from bedrock_agentcore.services.identity import IdentityClient
from bedrock_agentcore_starter_toolkit.utils.runtime.config import load_config, save_config
from bedrock_agentcore_starter_toolkit.utils.runtime.schema import CredentialProviderInfo, IdentityConfig
import boto3
import json
import logging
import os
import time
from pathlib import Path


def setup_gateway(
    name: str | None = None,
    region: str = "us-west-2",
    output_path: str = "gateway_config.json",
) -> dict:
    region = os.environ.get("GATEWAY_REGION", region)
    name = os.environ.get("GATEWAY_NAME", name)
    output_path = os.environ.get("GATEWAY_CONFIG", output_path)

    print(f"AgentCore Gateway をセットアップしています (リージョン: {region})...")

    client = GatewayClient(region_name=region)
    client.logger.setLevel(logging.WARNING)

    # Step 1: Create Cognito OAuth authorizer
    print("Cognito OAuth 認証サーバーを作成しています...")
    cognito_response = client.create_oauth_authorizer_with_cognito(name or "AgentCoreGateway")
    print("認証サーバーを作成しました。")

    # Step 2: Create Gateway
    print("Gateway を作成しています...")
    gateway = client.create_mcp_gateway(
        name=name,
        role_arn=None,
        authorizer_config=cognito_response["authorizer_config"],
        enable_semantic_search=True,
    )
    print(f"Gateway を作成しました: {gateway['gatewayUrl']}")

    # Fix IAM permissions and wait for propagation
    client.fix_iam_permissions(gateway)
    print("IAM 権限の反映を 30 秒待っています...")
    time.sleep(30)

    # Step 3: Create Identity Credential Provider
    config = {
        "gateway_url": gateway["gatewayUrl"],
        "gateway_id": gateway["gatewayId"],
        "region": region,
        "client_info": cognito_response["client_info"],
    }
    print("AgentCore Identity Credential Provider を作成しています...")
    provider_name = setup_identity_provider(config, region)
    config["provider_name"] = provider_name
    print(f"Credential Provider を作成しました: {provider_name}")

    # Step 4: Save configuration
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n完了！設定を保存しました: {output_path}")
    print(f"  Gateway URL:     {gateway['gatewayUrl']}")
    print(f"  Gateway ID:      {gateway['gatewayId']}")
    print(f"  Provider Name:   {provider_name}")

    return config


def setup_identity_provider(config: dict, region: str = "us-west-2") -> str:
    """
    AgentCore Identity に Cognito OAuth2 Credential Provider を作成する。
    既存の Gateway 設定に対して後から実行することもできる。

    前提: 'bedrock agentcore create' を先に実行して .bedrock_agentcore.yaml が存在すること。

    Returns:
        作成した credential provider の名前
    """
    client_info = config["client_info"]
    user_pool_id = client_info["user_pool_id"]
    gateway_id = config["gateway_id"]

    provider_name = f"gateway-cognito-{gateway_id[:12]}"
    domain_prefix = client_info["domain_prefix"]
    issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
    token_endpoint = client_info["token_endpoint"]
    authorization_endpoint = (
        f"https://{domain_prefix}.auth.{region}.amazoncognito.com/oauth2/authorize"
    )

    # Step 1: AgentCore Identity に Credential Provider を作成
    identity_client = IdentityClient(region)
    response = identity_client.create_oauth2_credential_provider({
        "name": provider_name,
        "credentialProviderVendor": "CognitoOauth2",
        "oauth2ProviderConfigInput": {
            "includedOauth2ProviderConfig": {
                "clientId": client_info["client_id"],
                "clientSecret": client_info["client_secret"],
                "issuer": issuer,
                "authorizationEndpoint": authorization_endpoint,
                "tokenEndpoint": token_endpoint,
            }
        },
    })
    provider_arn = response.get("credentialProviderArn", "")
    print(f"Credential Provider を作成しました: {provider_name} ({provider_arn})")

    # Step 2: .bedrock_agentcore.yaml から Runtime ロール情報を取得
    agentcore_yaml_path = Path(__file__).parent / ".bedrock_agentcore.yaml"
    if not agentcore_yaml_path.exists():
        raise FileNotFoundError(
            f"{agentcore_yaml_path} が見つかりません。"
            "先に 'bedrock agentcore create' を実行してください。"
        )

    project_config = load_config(agentcore_yaml_path)
    agent_config = project_config.get_agent_config()
    execution_role_arn = agent_config.aws.execution_role or ""
    account_id = agent_config.aws.account or ""

    if not execution_role_arn:
        raise ValueError(
            "execution_role が .bedrock_agentcore.yaml に設定されていません。"
            "先に 'bedrock agentcore create' を実行してください。"
        )

    # Step 3: Runtime 実行ロールに GetResourceOauth2Token 権限を付与
    role_name = execution_role_arn.split("/")[-1]
    iam = boto3.client("iam")
    iam.put_role_policy(
        RoleName=role_name,
        PolicyName="AgentCoreGetResourceOauth2Token",
        PolicyDocument=json.dumps({
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Action": "bedrock-agentcore:GetResourceOauth2Token",
                "Resource": (
                    f"arn:aws:bedrock-agentcore:{region}:{account_id}"
                    ":workload-identity-directory/default/workload-identity/*"
                ),
            }],
        }),
    )
    print(f"IAM権限を付与しました: {role_name}")

    # Step 4: .bedrock_agentcore.yaml を正式フォーマットで更新
    if not agent_config.identity:
        agent_config.identity = IdentityConfig()

    # 同名の古いエントリを除去してから追加（再実行時の重複・破損を防ぐ）
    agent_config.identity.credential_providers = [
        p for p in agent_config.identity.credential_providers
        if p.name != provider_name
    ]
    agent_config.identity.credential_providers.append(
        CredentialProviderInfo(
            name=provider_name,
            arn=provider_arn,
            type="cognito",
            callback_url="",
        )
    )
    project_config.agents[agent_config.name] = agent_config
    save_config(project_config, agentcore_yaml_path)
    print(f".bedrock_agentcore.yaml を更新しました (provider: {provider_name})")

    return provider_name


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "identity":
        # 既存のゲートウェイに対して Identity Provider だけ作成する場合:
        # python setup_gateway.py identity [config_path]
        config_path = sys.argv[2] if len(sys.argv) > 2 else "gateway_config.json"
        with open(config_path) as f:
            existing_config = json.load(f)
        region = existing_config.get("region", "us-west-2")
        print(f"既存の Gateway 設定に Identity Provider を追加します: {config_path}")
        provider_name = setup_identity_provider(existing_config, region)
        existing_config["provider_name"] = provider_name
        with open(config_path, "w") as f:
            json.dump(existing_config, f, indent=2)
        print(f"完了！provider_name を保存しました: {provider_name}")
    else:
        setup_gateway()

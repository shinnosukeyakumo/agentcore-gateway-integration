import json
import os
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity import requires_access_token

# gateway_config.json から設定を読み込む
_config_path = os.path.join(os.path.dirname(__file__), "gateway_config.json")
with open(_config_path) as f:
    _config = json.load(f)

_gateway_url = _config["gateway_url"]
_provider_name = _config["provider_name"]
_scope = _config["client_info"]["scope"]


@requires_access_token(
    provider_name=_provider_name,
    scopes=[_scope],
    auth_flow="M2M",
)
def _get_access_token(*, access_token: str) -> str:
    """AgentCore Identity 経由で M2M アクセストークンを取得する"""
    return access_token


app = BedrockAgentCoreApp()


@app.entrypoint
def invoke(payload):
    user_message = payload.get("prompt", "")

    token = _get_access_token()

    def transport_factory():
        return streamablehttp_client(
            _gateway_url,
            headers={"Authorization": f"Bearer {token}"},
        )

    with MCPClient(transport_factory) as mcp_client:
        agent = Agent(tools=mcp_client.list_tools_sync())
        response = agent(user_message)

    return str(response)


if __name__ == "__main__":
    app.run()

import json
import os
from strands import Agent
from strands.tools.mcp import MCPClient
from mcp.client.streamable_http import streamablehttp_client
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from bedrock_agentcore.identity import requires_access_token

# このファイル（agent-test.py）と同じディレクトリにある gateway_config.json を読み込む
# gateway_config.json には MCP ゲートウェイの URL や認証情報が書かれている
_config_path = os.path.join(os.path.dirname(__file__), "gateway_config.json")
with open(_config_path) as f:
    _config = json.load(f)

# 設定ファイルから必要な値を取り出す
_gateway_url = _config["gateway_url"]        # MCP ゲートウェイの接続先 URL
_provider_name = _config["provider_name"]    # アクセストークンを発行する認証プロバイダー名
_scope = _config["client_info"]["scope"]     # トークンに付与する権限スコープ（例: "mcp:invoke"）


# BedrockAgentCore アプリケーションのインスタンスを作成する
# このオブジェクトがエントリーポイントの登録やサーバー起動を管理する
app = BedrockAgentCoreApp()


# @app.entrypoint: この関数を AgentCore への呼び出し口として登録する
# @requires_access_token: 関数が実行される前に M2M（マシン間認証）でアクセストークンを取得し、
#   引数 access_token に自動で渡してくれるデコレーター
@app.entrypoint
@requires_access_token(
    provider_name=_provider_name,
    scopes=[_scope],
    auth_flow="M2M",
)
def invoke(payload, *, access_token: str):
    # リクエストのペイロードから "prompt" キーのテキストを取り出す
    # キーが無い場合は空文字列をデフォルト値として使う
    user_message = payload.get("prompt", "")

    # MCPClient に渡す「トランスポート（通信手段）」を生成する関数
    # Bearer トークンを Authorization ヘッダーに付けて HTTP ストリーミング接続を行う
    def transport_factory():
        return streamablehttp_client(
            _gateway_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    # MCPClient を使って MCP ゲートウェイに接続し、利用できるツール一覧を取得する
    # Agent にそのツール一覧を渡して初期化し、ユーザーのメッセージを処理する
    with MCPClient(transport_factory) as mcp_client:
        agent = Agent(tools=mcp_client.list_tools_sync())  # ツール付きエージェントを作成
        response = agent(user_message)                      # エージェントにメッセージを送り、応答を得る

    # 応答オブジェクトを文字列に変換して返す
    return str(response)


# スクリプトを直接実行したとき（python agent-test.py）にサーバーを起動する
if __name__ == "__main__":
    app.run()

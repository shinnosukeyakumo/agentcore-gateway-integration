# AgentCore Gateway Integration

Amazon Bedrock AgentCore の Gateway (MCP) に Strands Agents から接続するサンプルです。

Cognito OAuth (M2M) で認証し、AgentCore Identity 経由でアクセストークンを取得して Gateway の MCP ツールを呼び出します。

## アーキテクチャ

```
[Strands Agent]
    │  AgentCore Identity で M2M トークン取得
    ▼
[AgentCore Gateway (MCP)]
    │  Cognito OAuth で認証
    ▼
[MCP Tools]
```

## 前提条件

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- AWS CLI (`aws login` で認証済み)
- AWS リージョン: `us-west-2`

## セットアップ

### 1. 依存関係をインストール

```bash
cd src
uv venv
uv pip install -r requirements.txt
```

### 2. エージェントをデプロイ

IAM 実行ロールの自動作成と AgentCore Runtime へのデプロイを行います。

```bash
uv run bedrock-agentcore deploy
```

### 3. Gateway をセットアップ

Cognito OAuth 認証サーバー・Gateway・Credential Provider を一括作成します。

```bash
uv run setup_gateway.py
```

完了すると `gateway_config.json` が生成されます（※ Git 管理外）。

### 4. 再デプロイ（Observability 有効化）

`aws-opentelemetry-distro` を有効にするため再デプロイが必要です。

```bash
uv run bedrock-agentcore deploy
```

## ファイル構成

```
src/
├── agent-test.py        # エージェント本体
├── setup_gateway.py     # Gateway セットアップスクリプト
├── requirements.txt     # 依存パッケージ
└── gateway_config.json  # 自動生成（Git 管理外）
```

## 環境変数（オプション）

`setup_gateway.py` の動作を変更したい場合は環境変数で指定できます。

| 変数名 | デフォルト | 説明 |
|---|---|---|
| `GATEWAY_REGION` | `us-west-2` | AWS リージョン |
| `GATEWAY_NAME` | 自動生成 | Gateway 名 |
| `GATEWAY_CONFIG` | `gateway_config.json` | 出力先パス |

## 注意事項

- `gateway_config.json` には Cognito の `client_secret` が含まれるため、Git にコミットしないでください。
- `.bedrock_agentcore.yaml` には IAM ロール ARN などのアカウント固有情報が含まれます。

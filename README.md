# AgentCore Gateway Integration

Amazon Bedrock AgentCore の Gateway (MCP) に AgentCore RuntimeにデプロイしたStrands Agentsから接続するサンプルです。

Cognito OAuth (M2M) で認証し、AgentCore Identity 経由でアクセストークンを取得して Gateway の MCP ツールを呼び出します。

## アーキテクチャ

```
[AgentCore Runtime(Strands Agent)]
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

### 1. 仮想環境を作成してパッケージをインストール

```bash
cd src
uv venv
source .venv/bin/activate   # Windows の場合: .venv\Scripts\activate
uv pip install -r requirements.txt
```

インストールされるパッケージ：

| パッケージ | 役割 |
|---|---|
| `strands-agents[otel]` | Strands エージェントフレームワーク（OpenTelemetry 計装付き） |
| `bedrock-agentcore` | AgentCore Runtime へのデプロイ CLI |
| `aws-opentelemetry-distro` | AWS 向け OpenTelemetry ディストリビューション |

### 2. エージェントの初期設定

AgentCore エージェントの初期設定（IAM 実行ロール・リージョン・エントリポイントなど）を行います。

```bash
uv run bedrock-agentcore configure
```

対話形式でリージョンや実行ロールなどが設定され、`src/.bedrock_agentcore.yaml` が生成されます。

### 3. エージェントをデプロイ

IAM 実行ロールの自動作成と AgentCore Runtime へのデプロイを行います。

```bash
uv run bedrock-agentcore deploy
```

### 4. Gateway をセットアップ

Cognito OAuth 認証サーバー・Gateway・Credential Provider を一括作成します。

```bash
uv run setup_gateway.py
```

完了すると `gateway_config.json` が生成されます（※ Git 管理外）。

### 5. 再デプロイ

jsonファイルの環境変数を有効にするため再デプロイが必要です。

```bash
uv run bedrock-agentcore deploy
```

## ファイル構成

```
src/
├── agent-test.py              # エージェント本体
├── setup_gateway.py           # Gateway セットアップスクリプト
├── requirements.txt           # 依存パッケージ
├── .bedrock_agentcore.yaml    # configure で自動生成（IAMロール・ARNなど）
└── gateway_config.json        # setup_gateway.py で自動生成（Git 管理外）
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

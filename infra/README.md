# Meeting Minutes インフラストラクチャ — デプロイ手順

## 概要

このディレクトリには、Meeting Minutes SaaS アプリケーションの AWS インフラストラクチャを定義する Terraform 構成ファイルが含まれています。

すべてのリソースは `ap-northeast-1` リージョンにデプロイされ、MZJ-IAM ポリシーに準拠しています。

## 前提条件

以下のツールがインストールされている必要があります：

| ツール | バージョン | 用途 |
|--------|-----------|------|
| Terraform | >= 1.5.0 | インフラストラクチャのプロビジョニング |
| AWS CLI | v2 | S3 同期、CloudFront 無効化 |
| Node.js | >= 18 | フロントエンドのビルド |
| Python | >= 3.12 | Lambda 関数の依存関係 |
| pip | 最新 | Python パッケージのインストール |

## AWS プロファイルの設定

Terraform は `terraform` という名前の AWS CLI プロファイルを使用します。まだ設定していない場合：

```bash
aws configure --profile terraform
# AWS Access Key ID: <あなたのアクセスキー>
# AWS Secret Access Key: <あなたのシークレットキー>
# Default region name: ap-northeast-1
# Default output format: json
```

## デプロイ手順

### ステップ 1: Terraform の初期化

```bash
cd infra
terraform init
```

初回実行時に AWS プロバイダーがダウンロードされます。

### ステップ 2: デプロイ計画の確認

```bash
terraform plan
```

作成されるリソースの一覧が表示されます（約 120 リソース）。以下が含まれます：

- Amazon Cognito ユーザープール + アプリクライアント
- API Gateway（REST + WebSocket）
- Lambda 関数 × 9（IAM ロール付き）
- Step Functions ステートマシン
- S3 バケット × 3（データ、プロンプト、フロントエンド）
- DynamoDB テーブル
- Bedrock ガードレール
- CloudFront ディストリビューション

### ステップ 3: リソースのデプロイ

```bash
terraform apply
```

確認プロンプトで `yes` と入力します。デプロイには 5〜10 分かかります。

### ステップ 4: 出力値の確認

デプロイ完了後、重要な出力値を確認します：

```bash
terraform output
```

主な出力値：

| 出力名 | 説明 |
|--------|------|
| `cognito_user_pool_id` | Cognito ユーザープール ID |
| `cognito_app_client_id` | Cognito アプリクライアント ID |
| `rest_api_endpoint` | REST API エンドポイント URL |
| `ws_api_endpoint` | WebSocket API エンドポイント URL |
| `cloudfront_distribution_domain_name` | フロントエンドの CloudFront ドメイン |
| `s3_frontend_bucket_name` | フロントエンド S3 バケット名 |
| `bedrock_guardrail_id` | Bedrock ガードレール ID |

### ステップ 5: フロントエンドの環境変数を設定

Terraform の出力値を使って、フロントエンドの環境変数ファイルを作成します：

```bash
cd ../frontend
cp .env.local.example .env.local
```

`.env.local` を編集し、Terraform の出力値を設定します：

```bash
# Terraform の出力値から取得
NEXT_PUBLIC_COGNITO_USER_POOL_ID=$(terraform -chdir=../infra output -raw cognito_user_pool_id)
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=$(terraform -chdir=../infra output -raw cognito_app_client_id)
NEXT_PUBLIC_API_GATEWAY_URL=$(terraform -chdir=../infra output -raw rest_api_endpoint)
NEXT_PUBLIC_WEBSOCKET_URL=$(terraform -chdir=../infra output -raw ws_api_endpoint)
```

または、以下のワンライナーで `.env.local` を自動生成できます：

```bash
cat > frontend/.env.local << EOF
NEXT_PUBLIC_COGNITO_USER_POOL_ID=$(terraform -chdir=infra output -raw cognito_user_pool_id)
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=$(terraform -chdir=infra output -raw cognito_app_client_id)
NEXT_PUBLIC_API_GATEWAY_URL=$(terraform -chdir=infra output -raw rest_api_endpoint)
NEXT_PUBLIC_WEBSOCKET_URL=$(terraform -chdir=infra output -raw ws_api_endpoint)
EOF
```

### ステップ 6: Lambda 関数のデプロイ

Terraform はプレースホルダーコードで Lambda 関数をデプロイします。このステップで実際のハンドラーに置き換えます。

自動化スクリプトがすべてを処理します — 依存関係レイヤーの作成、アタッチ、各ハンドラーの共有モジュール付きパッケージング、デプロイ：

```bash
# プロジェクトルートから実行
chmod +x scripts/deploy-lambdas.sh
./scripts/deploy-lambdas.sh
```

スクリプトは以下の 3 つを実行します：

1. **Lambda レイヤーの作成** — Python 依存関係（`boto3`、`jsonschema`、`tiktoken`、`PyJWT`、`cryptography`）をインストールしてパブリッシュします。レイヤーが既に存在する場合は再利用します。

2. **レイヤーのアタッチ** — 全 9 つの Lambda 関数にレイヤーをアタッチし、ランタイムで依存関係をインポートできるようにします。

3. **パッケージングとデプロイ** — 9 つの Lambda 関数それぞれをパッケージングしてデプロイします。各 ZIP には以下が含まれます：
   - ハンドラーファイル（`handler.py`）
   - ハンドラーがインポートする共有モジュール（`backend/models/`、`backend/utils/`）

デプロイされる 9 つの Lambda 関数：

| 関数名 | ソースディレクトリ | 用途 |
|--------|-------------------|------|
| `Pranav-meeting-minutes-ws-authorizer` | `backend/lambdas/ws_authorizer/` | WebSocket JWT 検証 |
| `Pranav-meeting-minutes-ws-handler` | `backend/lambdas/ws_handler/` | WebSocket 接続ルーティング |
| `Pranav-meeting-minutes-stream-bridge` | `backend/lambdas/stream_bridge/` | 音声 → Transcribe ブリッジ |
| `Pranav-meeting-minutes-api` | `backend/lambdas/api/` | REST API CRUD 操作 |
| `Pranav-meeting-minutes-cleanup` | `backend/lambdas/cleanup/` | トランスクリプトクリーンアップ |
| `Pranav-meeting-minutes-chunker` | `backend/lambdas/chunker/` | トランスクリプトチャンキング |
| `Pranav-meeting-minutes-generator` | `backend/lambdas/generator/` | 議事録生成（Bedrock） |
| `Pranav-meeting-minutes-validator` | `backend/lambdas/validator/` | スキーマバリデーション |
| `Pranav-meeting-minutes-store` | `backend/lambdas/store/` | レポートストレージ + ステータス |

### ステップ 7: Bedrock ガードレール ID の更新

Bedrock ガードレールがデプロイされたら、Generator Lambda の環境変数を更新します：

```bash
GUARDRAIL_ID=$(terraform -chdir=infra output -raw bedrock_guardrail_id)
GUARDRAIL_VERSION=$(terraform -chdir=infra output -raw bedrock_guardrail_version)

aws lambda update-function-configuration \
  --function-name Pranav-meeting-minutes-generator \
  --environment "Variables={PROMPT_BUCKET=$(terraform -chdir=infra output -raw s3_prompts_bucket_name),PROMPT_VERSION=v1,GUARDRAIL_ID=$GUARDRAIL_ID,GUARDRAIL_VERSION=$GUARDRAIL_VERSION,MODEL_ID=anthropic.claude-3-haiku-20240307-v1:0}" \
  --profile terraform \
  --region ap-northeast-1
```

### ステップ 8: フロントエンドのデプロイ

```bash
chmod +x scripts/deploy-frontend.sh
./scripts/deploy-frontend.sh
```

このスクリプトは以下を実行します：
1. Next.js アプリをビルド
2. ビルド出力を S3 フロントエンドバケットに同期
3. CloudFront キャッシュを無効化

### ステップ 9: 動作確認

CloudFront のドメイン名でアプリにアクセスします：

```bash
echo "https://$(terraform -chdir=infra output -raw cloudfront_distribution_domain_name)"
```

## 動作テスト

### 1. ユーザー登録とログイン

1. CloudFront URL にアクセス
2. 「Create Account」をクリック
3. メールアドレス、パスワード、名前を入力
4. メールに届く確認コードを入力
5. ログインページでサインイン

### 2. 会議キャプチャのテスト

1. ログイン後、「/capture」ページに移動
2. 「Start Meeting Capture」をクリック
3. マイクへのアクセスを許可
4. 録音インジケーター（赤い点滅 + タイマー）が表示されることを確認
5. ライブトランスクリプトパネルにテキストが表示されることを確認
6. 「Stop and Generate Minutes」をクリック
7. 処理ステータスが表示されることを確認
8. 生成された議事録レポートが表示されることを確認

### 3. レポートの確認

1. 「/meetings」ページで会議一覧を確認
2. 完了した会議をクリックしてレポートを表示
3. インライン編集が機能することを確認
4. 「Copy to Clipboard」と「Download JSON」が機能することを確認

## トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| `terraform apply` が IAM エラーで失敗 | MZJTeamBoundary ポリシーが存在することを確認 |
| Lambda 関数がタイムアウト | CloudWatch ログを確認（`/aws/lambda/Pranav-meeting-minutes-*`） |
| WebSocket 接続が失敗 | ブラウザの開発者ツールでコンソールエラーを確認 |
| Bedrock 呼び出しが失敗 | `ap-northeast-1` で Claude 3 Haiku モデルへのアクセスが有効か確認 |
| フロントエンドが 403 を返す | CloudFront の OAC 設定と S3 バケットポリシーを確認 |
| CORS エラー | API Gateway の CORS 設定を確認 |

## リソースの削除

すべてのリソースを削除するには：

```bash
# まず S3 バケットの中身を空にする（バージョニング有効のため）
aws s3 rm s3://pranav-meeting-minutes-data --recursive --profile terraform
aws s3 rm s3://pranav-meeting-minutes-prompts --recursive --profile terraform
aws s3 rm s3://pranav-meeting-minutes-frontend --recursive --profile terraform

# Terraform でリソースを削除
cd infra
terraform destroy
```

確認プロンプトで `yes` と入力します。

## Terraform ファイル構成

| ファイル | 内容 |
|---------|------|
| `provider.tf` | AWS プロバイダー設定（ap-northeast-1、terraform プロファイル） |
| `variables.tf` | 共有変数（リージョン、プロジェクト名、ユーザー名） |
| `locals.tf` | 共通タグ、パーミッションバウンダリ、命名プレフィックス |
| `cognito.tf` | Cognito ユーザープール + アプリクライアント |
| `api_gateway_rest.tf` | REST API Gateway + Cognito オーソライザー |
| `api_gateway_ws.tf` | WebSocket API Gateway + Lambda オーソライザー |
| `s3.tf` | S3 バケット（データ、プロンプト） |
| `s3_objects.tf` | プロンプトテンプレートとスキーマの S3 アップロード |
| `dynamodb.tf` | DynamoDB 接続テーブル |
| `iam.tf` | IAM ロール + ポリシー（全 Lambda + Step Functions） |
| `lambda.tf` | Lambda 関数 × 9 + CloudWatch ロググループ |
| `step_functions.tf` | Step Functions ステートマシン |
| `bedrock.tf` | Bedrock ガードレール |
| `frontend.tf` | S3 + CloudFront フロントエンドホスティング |
| `outputs.tf` | Terraform 出力値 |

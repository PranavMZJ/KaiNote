# KaiNote インフラストラクチャ — デプロイ手順

## 概要

このディレクトリには、KaiNote 議事録アプリケーションの AWS インフラストラクチャを定義する Terraform 構成ファイルが含まれています。リアルタイム音声文字起こし、ライブ翻訳、AI 議事録生成、自動フォローアップアクションを提供します。

**リージョン:** `ap-northeast-1`（東京）
**命名規則:** `Pranav-meeting-minutes-{purpose}`
**タグ:** `User=Pranav`, `Project=meeting-minutes`

## 前提条件

| ツール | バージョン | 用途 |
|--------|-----------|------|
| Terraform | >= 1.5.0 | インフラプロビジョニング |
| AWS CLI | v2 | デプロイ、S3 同期 |
| Node.js | >= 18 | フロントエンドビルド |
| Python | >= 3.12 | Lambda 依存関係 |
| Docker | 最新 | ECS Fargate コンテナビルド |
| pip | 最新 | Python パッケージ |

## AWS プロファイル設定

```bash
aws configure --profile terraform
# AWS Access Key ID: <アクセスキー>
# AWS Secret Access Key: <シークレットキー>
# Default region name: ap-northeast-1
# Default output format: json
```

## 詳細デプロイ手順

### ステップ 1: Terraform Init & Apply

```bash
cd infra
terraform init
terraform plan    # 約 130 リソースを確認
terraform apply   # 'yes' を入力 — 5〜10 分
```

作成されるリソース：
- CloudFront ディストリビューション（SPA + WebSocket プロキシ）
- Cognito ユーザープール + アプリクライアント
- API Gateway（REST + WebSocket）
- Lambda 関数 × 10（IAM ロール付き）
- ECS Fargate クラスター + サービス + ALB
- ECR リポジトリ
- VPC（パブリック + プライベートサブネット、NAT Gateway）
- Step Functions ステートマシン
- S3 バケット × 3（データ、プロンプト、フロントエンド）
- DynamoDB テーブル × 3（meetings、connections、audio_buffer）
- SNS トピック + メールサブスクリプション
- Bedrock ガードレール
- CloudWatch ロググループ

### ステップ 2: フロントエンド環境変数

```bash
cat > frontend/.env.local << EOF
NEXT_PUBLIC_COGNITO_USER_POOL_ID=$(terraform -chdir=infra output -raw cognito_user_pool_id)
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=$(terraform -chdir=infra output -raw cognito_app_client_id)
NEXT_PUBLIC_API_GATEWAY_URL=$(terraform -chdir=infra output -raw rest_api_endpoint)
NEXT_PUBLIC_WEBSOCKET_URL=$(terraform -chdir=infra output -raw ws_api_endpoint)
NEXT_PUBLIC_TRANSCRIPTION_WS_URL=wss://$(terraform -chdir=infra output -raw cloudfront_distribution_domain_name)
EOF
```

### ステップ 3: Lambda 関数のデプロイ

```bash
chmod +x scripts/deploy-lambdas.sh
./scripts/deploy-lambdas.sh
```

| 関数名 | 用途 |
|--------|------|
| `Pranav-meeting-minutes-ws-authorizer` | WebSocket JWT 検証 |
| `Pranav-meeting-minutes-ws-handler` | WebSocket 接続ルーティング |
| `Pranav-meeting-minutes-stream-bridge` | 音声 → Transcribe ブリッジ（レガシー） |
| `Pranav-meeting-minutes-api` | REST API（会議 CRUD、レポート、エージェントレポート） |
| `Pranav-meeting-minutes-cleanup` | トランスクリプトクリーンアップ |
| `Pranav-meeting-minutes-chunker` | トランスクリプトチャンキング |
| `Pranav-meeting-minutes-generator` | 議事録生成（Bedrock + RAG） |
| `Pranav-meeting-minutes-validator` | JSON Schema バリデーション |
| `Pranav-meeting-minutes-store` | レポート保存 + DynamoDB ステータス |
| `Pranav-meeting-minutes-agent` | ポストミーティングエージェント（通知、期限超過検出） |

### ステップ 4: 文字起こしサービスのデプロイ（ECS Fargate）

```bash
chmod +x scripts/deploy-transcription-service.sh
./scripts/deploy-transcription-service.sh
```

文字起こしサービスの機能：
- リアルタイム音声文字起こし（Amazon Transcribe Streaming）
- ライブ翻訳（Amazon Translate）— 7 言語対応
- 話者再帰属（Bedrock による文脈分析）
- 多言語対応（en-US, ja-JP, ko-KR, zh-CN, fr-FR, de-DE, es-ES）

### ステップ 5: フロントエンドのデプロイ

```bash
chmod +x scripts/deploy-frontend.sh
./scripts/deploy-frontend.sh
```

### ステップ 6: SNS メールサブスクリプションの確認

デプロイ後、AWS から確認メールが届きます。メール内のリンクをクリックして通知を有効化してください。

### ステップ 7: アプリにアクセス

```bash
echo "https://$(terraform -chdir=infra output -raw cloudfront_distribution_domain_name)"
```

## アプリのテスト

### 1. ユーザー登録 & ログイン
1. CloudFront URL を開く
2. 「Create Account」→ メール、パスワードを入力
3. メールに届く確認コードを入力
4. サインイン

### 2. 会議キャプチャ
1. `/capture` ページに移動
2. **Audio Language** を選択（English または 日本語）
3. **Display Transcription In** でライブ翻訳言語を選択（任意）
4. 「Start Meeting Capture」→ マイクを許可
5. 音声を話すか再生 → リアルタイムで文字起こしが表示
6. 「Stop and Generate Minutes」をクリック
7. `/meetings` に自動遷移 → ステータスが「Processing」→「Completed」に自動更新

### 3. レポート確認
1. `/meetings` で完了した会議をクリック
2. レポート表示：要約、決定事項、アクションアイテム、リスク
3. レポート下部：「🤖 Automated Actions」— 通知送信、期限超過、フォローアップ提案
4. ⋮ メニュー：レポートダウンロード、共有、削除

### 4. テスト用音声ファイル
`docs/Testing/` にテスト用音声があります：
- `test-product-launch-meeting.mp3` — 英語の製品発売レビュー
- `test-japanese-sprint-review.mp3` — 日本語のスプリントレビュー
- `product-launch-series/` — RAG テスト用 3 会議シリーズ

## アーキテクチャ

詳細は `docs/images/architecture-current.md` を参照。

```
Browser → CloudFront → ALB → ECS Fargate → Transcribe Streaming
                                          → Amazon Translate（ライブ翻訳）
                                          → Bedrock（話者再帰属）
                                          → S3（トランスクリプト保存）
                                          → Step Functions（後処理）
                                               → Cleanup → Chunker → Generator（Bedrock + RAG）
                                               → Validator → Store → Agent（Bedrock + SNS）
```

## トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| `terraform apply` IAM エラー | `MZJTeamBoundary` ポリシーの存在を確認 |
| Lambda タイムアウト | CloudWatch ログ確認: `/aws/lambda/Pranav-meeting-minutes-*` |
| WebSocket 接続失敗 | ブラウザをハードリフレッシュ（Cmd+Shift+R） |
| Bedrock 失敗 | ap-northeast-1 で Claude モデルアクセスが有効か確認 |
| ECS タスク再起動 | `/ecs/Pranav-meeting-minutes-transcription` ログ確認 |
| ライブ文字起こし不動作 | ECS サービスが稼働中か確認 |
| 翻訳が動作しない | ECS タスクロールに `translate:TranslateText` 権限があるか確認 |
| SNS メール未着 | サブスクリプション確認メールを確認（迷惑メールフォルダも） |
| フロントエンドが古い | CloudFront 無効化に 1-2 分かかる；ハードリフレッシュ |
| レポートが間違った言語 | 「Audio Language」ドロップダウンが実際の音声と一致しているか確認 |

## リソースの削除

```bash
# 1. S3 バケットを空にする
aws s3 rm s3://pranav-meeting-minutes-data --recursive --profile terraform
aws s3 rm s3://pranav-meeting-minutes-prompts --recursive --profile terraform
aws s3 rm s3://pranav-meeting-minutes-frontend --recursive --profile terraform

# 2. ECR イメージを削除
aws ecr batch-delete-image --repository-name pranav-meeting-minutes-transcription \
  --image-ids "$(aws ecr list-images --repository-name pranav-meeting-minutes-transcription --profile terraform --region ap-northeast-1 --query 'imageIds[*]' --output json)" \
  --profile terraform --region ap-northeast-1 2>/dev/null || true

# 3. インフラを削除
cd infra
terraform destroy   # 'yes' を入力
```

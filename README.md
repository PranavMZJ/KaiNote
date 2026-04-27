# Meeting Minutes — AI 議事録自動生成アプリケーション

ブラウザから会議音声をキャプチャし、リアルタイムで文字起こしを行い、AI が構造化された議事録レポートを自動生成する SaaS アプリケーションです。

## アーキテクチャ

![AWS アーキテクチャ図](docs/images/meeting-minutes-architecture.drawio.svg)

## 主な機能

- **ライブ音声キャプチャ** — ブラウザのマイクから会議音声をリアルタイムでキャプチャ
- **リアルタイム文字起こし** — Amazon Transcribe Streaming による話者ラベル付きライブトランスクリプト
- **AI 議事録生成** — Amazon Bedrock（Claude 3 Haiku）が構造化された議事録を自動生成
  - 会議の要約
  - 議題 / 議論のポイント
  - 決定事項（根拠・担当者・エビデンス付き）
  - アクションアイテム（担当者・期限・優先度・信頼度スコア付き）
  - リスク / ブロッカー
  - 未解決事項
- **人間レビュー支援** — 信頼度の低いアイテムを自動フラグ、未設定の担当者・期限をハイライト
- **インライン編集** — 生成された議事録をブラウザ上で直接編集・保存
- **エクスポート** — クリップボードコピー、JSON ダウンロード
- **セキュリティ** — Amazon Cognito 認証、ユーザーごとのデータ分離、最小権限 IAM、Bedrock Guardrails
- **サーバーレス** — 全コンポーネントが従量課金、アイドル時のコストはほぼゼロ

## 技術スタック

| レイヤー | 技術 |
|---------|------|
| フロントエンド | React / Next.js（静的エクスポート）、S3 + CloudFront |
| 認証 | Amazon Cognito User Pool |
| API | API Gateway（REST + WebSocket） |
| バックエンド | AWS Lambda（Python 3.12）× 9 関数 |
| 文字起こし | Amazon Transcribe Streaming |
| AI / ML | Amazon Bedrock（Claude 3 Haiku）+ Guardrails |
| オーケストレーション | AWS Step Functions |
| ストレージ | Amazon S3、Amazon DynamoDB |
| 監視 | Amazon CloudWatch |
| IaC | Terraform |
| UI デザイン | Lusion インスパイアのダークテーマ |

## プロジェクト構成

```
.
├── backend/                  # Python Lambda 関数
│   ├── lambdas/              # 9 つの Lambda ハンドラー
│   ├── models/               # データモデル（dataclass）
│   ├── prompts/              # Bedrock プロンプトテンプレート
│   ├── schemas/              # Minutes Schema（JSON Schema）
│   └── utils/                # 共有ユーティリティ
├── frontend/                 # React / Next.js フロントエンド
│   └── src/
│       ├── api/              # 型付き API クライアント
│       ├── app/              # ページ（login, capture, meetings）
│       ├── auth/             # Cognito 認証モジュール
│       ├── capture/          # 音声キャプチャ + WebSocket
│       ├── components/       # UI コンポーネント
│       └── styles/           # デザインシステム
├── infra/                    # Terraform インフラストラクチャ
├── tests/                    # ユニットテスト + プロパティテスト
├── scripts/                  # デプロイスクリプト
└── docs/                     # ドキュメント + アーキテクチャ図
```

## デプロイ

デプロイ手順は **[infra/README.md](infra/README.md)** を参照してください。

## コスト見積もり

AWS コストの詳細な内訳は **[infra/cost_estimation.md](infra/cost_estimation.md)** を参照してください。

## テストの実行

```bash
# Python バックエンドテスト（208 テスト）
pip install -r backend/requirements.txt -r tests/requirements.txt
pytest tests/ -v

# フロントエンドテスト（23 テスト）
cd frontend && npm test
```

## 今後の改善予定

- **Amazon Bedrock Agents** — 議事録生成後のフォローアップワークフローを自律的に実行（Slack 通知、Jira チケット作成、カレンダー登録など）
- **Bedrock Knowledge Bases + RAG** — 社内ドキュメントやプロジェクト資料を参照し、より文脈に沿った議事録を生成
- **話者識別の改善** — 参加者名と話者ラベルの自動マッピング
- **Google Meet / Zoom 連携** — 録画ファイルの自動インポート
- **PDF / DOCX エクスポート** — フォーマット済みドキュメントの出力
- **会議履歴検索** — 過去の議事録を横断検索
- **会議分析ダッシュボード** — 会議時間、決定事項数、アクションアイテム完了率などの可視化
- **AWS WAF** — Web アプリケーションファイアウォールによるセキュリティ強化
- **DynamoDB メタデータ層** — 会議メタデータの高速クエリ対応

## MZJ-IAM 規約

このプロジェクトは MZJ-IAM ポリシーに準拠しています：

- リソース命名: `Pranav-meeting-minutes-{purpose}`
- タグ: `User=Pranav`, `Project=meeting-minutes`
- リージョン: `ap-northeast-1`

# KaiNote — AWS アーキテクチャ

<div align="center">
  <img src="../docs/images/svg/KaiNote-architecture.drawio.svg" alt="KaiNote AWS アーキテクチャ" width="100%">
</div>

<br/>

## なぜこのアーキテクチャか？

KaiNote は特定の問題を解決します：**会議音声をリアルタイムでキャプチャし、文字起こしを行い、AI が構造化レポートを生成する** — 会議終了後数秒以内に。

これには以下が必要です：
- 音声ストリーミング用の永続的 WebSocket 接続（Lambda のリクエスト-レスポンスモデルでは不可能）
- Amazon Transcribe Streaming とのリアルタイム双方向通信
- 障害を適切に処理する後処理オーケストレーション
- セキュアなユーザーごとのデータ分離

アーキテクチャは**可能な限りサーバーレス**（Lambda、Step Functions、S3、DynamoDB）を使用し、**必要な場合のみコンテナ**（長時間実行 WebSocket 文字起こしサービス用の ECS）を使用します。

---

## データフロー — キャプチャからレポートまで

### フェーズ 1: ライブキャプチャ & 文字起こし

```
ユーザーのブラウザ
    │
    │ 1. ユーザーが「会議キャプチャ開始」をクリック
    │    音声言語: en-US / ja-JP 等
    │    表示言語: 同じ or 翻訳
    │
    ▼
CloudFront (CDN)
    │
    │ 2. WebSocket 接続を ALB にプロキシ
    │    (wss:// → CloudFront → ALB オリジン)
    │
    ▼
Application Load Balancer (ALB)
    │
    │ 3. 正常な ECS コンテナにルーティング
    │    ヘルスチェック: GET /health → 200 OK
    │
    ▼
ECS EC2 — 文字起こしサービス (t3.micro, プライベートサブネット)
    │
    │ 4. 開始メッセージ受信: {meetingId, userId, audioLanguage, displayLanguage}
    │ 5. Amazon Transcribe Streaming セッション開始
    │
    │    === 音声ループ (会議中繰り返し) ===
    │    |
    │    |  Browser → PCM バイナリチャンク送信 (16bit, 16kHz)
    │    |       ↓
    │    |  ECS → Transcribe Streaming に転送
    │    |       ↓
    │    |  Transcribe → テキストセグメント返却 (話者付き)
    │    |       ↓
    │    |  [翻訳有効の場合] ECS → Amazon Translate → 翻訳テキスト
    │    |       ↓
    │    |  ECS → WebSocket → ブラウザに送信
    │    |
    │    =====================================
    │
    │ 6. ユーザーが「停止して議事録生成」をクリック
    │
    ▼
ECS — キャプチャ後処理
    │
    │ 7. Amazon Bedrock (Claude Haiku 4.5) で話者再帰属
    │    → 会話コンテキストから話者名を特定
    │
    │ 8. 生トランスクリプトを S3 に保存
    │    → s3://pranav-meeting-minutes-data/users/{userId}/transcripts/{meetingId}/raw.json
    │
    │ 9. DynamoDB に会議レコード作成 (status: "processing")
    │
    │ 10. Step Functions 実行開始
    │
    │ 11. {type: "capture_stopped"} をブラウザに送信 → /meetings にリダイレクト
    │
    ▼
```

### フェーズ 2: AI レポート生成 (Step Functions)

```
Step Functions ワークフロー
    │
    ├── ステップ 1: LoadTranscript (Cleanup Lambda)
    │   └── S3 から raw.json を読込
    │
    ├── ステップ 2: CleanTranscript (Cleanup Lambda)
    │   └── フィラーワード除去、フォーマット正規化
    │   └── cleaned.json を S3 に保存
    │   └── totalTokenCount 計算
    │
    ├── ステップ 3: CheckTokenCount (分岐)
    │   ├── ≤ 10,000 トークン → GenerateMinutes
    │   └── > 10,000 トークン → ChunkTranscript → GenerateMinutesChunked → MergeResults
    │
    ├── ステップ 4: GenerateMinutes (Generator Lambda)
    │   ├── S3 からプロンプトテンプレート読込 (prompts/v1/minutes_prompt.txt)
    │   ├── 過去会議コンテキスト取得 — RAG (直近 3 件のレポートを S3 から)
    │   ├── Amazon Bedrock (Claude Haiku 4.5) + Guardrails 呼出
    │   └── 構造化 JSON 返却: タイトル、要約、決定事項、アクションアイテム、リスク
    │
    ├── ステップ 5: ValidateSchema (Validator Lambda)
    │   ├── JSON Schema でバリデーション
    │   ├── 無効 → 生成リトライ (最大 3 回)
    │   └── 有効 → 続行
    │
    ├── ステップ 6: StoreReport (Store Lambda)
    │   ├── レポートを S3 に保存 (users/{userId}/reports/{meetingId}/minutes.json)
    │   └── DynamoDB ステータス更新 → "completed"
    │
    ├── ステップ 7: RunAgent (Agent Lambda) — ノンブロッキング
    │   ├── レポート + 過去会議コンテキスト (RAG) 読込
    │   ├── Bedrock で分析: 期限超過アイテム、フォローアップ必要性
    │   ├── SNS でアクションアイテム担当者にメール通知送信
    │   ├── agent_actions.json を S3 に保存
    │   └── ここでの失敗は会議を失敗にしない — レポートは既に保存済み
    │
    └── ステップ 8: UpdateStatus (Store Lambda)
        └── DynamoDB の最終タイムスタンプ更新
```

### フェーズ 3: ユーザーがレポートを閲覧

```
ユーザーのブラウザ (/meetings ページ)
    │
    │ status = "processing" の間、5秒ごとに自動ポーリング
    │
    ▼
API Gateway REST API + Cognito オーソライザー
    │
    ▼
Lambda: REST API
    │
    ├── GET /meetings → DynamoDB クエリ (userId パーティションキー)
    ├── GET /meetings/{id}/report → S3 取得 (minutes.json or minutes_edited.json)
    ├── GET /meetings/{id}/agent-report → S3 取得 (agent_actions.json)
    ├── PUT /meetings/{id}/report → S3 保存 (minutes_edited.json)
    └── DELETE /meetings/{id} → DynamoDB 削除 + S3 削除
```

---

## サービス責務

| サービス | 使用理由 | 役割 |
|---------|---------|------|
| **CloudFront** | 単一エントリポイント、HTTPS、キャッシュ | フロントエンド配信 (S3) + WebSocket プロキシ (ALB) |
| **S3 (フロントエンド)** | 静的ホスティング | Next.js ビルド出力を保存 |
| **Cognito** | 認証を自前で構築不要 | ユーザー登録、ログイン、JWT トークン |
| **API Gateway REST** | 認証付きマネージド API | Cognito 検証付きで Lambda にルーティング |
| **Lambda: API** | サーバーレス CRUD | 会議一覧、レポート取得、削除、リトライ |
| **ALB** | WebSocket ルーティング + ヘルスチェック | ブラウザ WebSocket を ECS コンテナにルーティング |
| **ECS EC2 (t3.micro)** | 長時間実行 WebSocket | 音声ストリーミング用の永続接続を維持 |
| **Transcribe Streaming** | リアルタイム STT | 音声ストリームを話者ラベル付きテキストに変換 |
| **Amazon Translate** | ライブ翻訳 | トランスクリプトセグメントを対象言語に翻訳 |
| **Bedrock (Claude Haiku 4.5)** | AI 分析 | レポート生成、話者再帰属、エージェント分析 |
| **Bedrock Guardrails** | コンテンツ安全性 | AI 出力から不適切なコンテンツをフィルタ |
| **Step Functions** | ワークフローオーケストレーション | リトライ付きマルチステップレポート生成パイプライン管理 |
| **Lambda: Cleanup** | テキスト正規化 | フィラーワード除去、話者セグメント結合 |
| **Lambda: Chunker** | 長い会議対応 | モデルコンテキストウィンドウ超過時にトランスクリプト分割 |
| **Lambda: Generator** | レポート生成 | プロンプト構築 (RAG 付き)、Bedrock 呼出、レスポンス解析 |
| **Lambda: Validator** | 品質ゲート | AI 出力を JSON Schema でバリデーション |
| **Lambda: Store** | 永続化 | レポートを S3 に保存、DynamoDB ステータス更新 |
| **Lambda: Agent** | ミーティング後自動化 | 通知、期限超過検出、フォローアップ提案 |
| **S3 (データ)** | 耐久性のあるストレージ | トランスクリプト、レポート、エージェントアクション |
| **S3 (プロンプト)** | テンプレート保存 | バージョン管理されたプロンプトテンプレートと JSON スキーマ |
| **DynamoDB** | 高速メタデータ | 会議レコード (ステータス、タイムスタンプ、キー) |
| **SNS** | 通知 | アクションアイテム担当者にメール送信 |
| **VPC + NAT Gateway** | ネットワークセキュリティ | ECS はプライベートサブネット、外部通信は NAT 経由 |
| **CloudWatch** | 可観測性 | 全 Lambda、ECS、Step Functions のログ |

---

## セキュリティモデル

- **認証:** 全 API コールに Cognito JWT
- **データ分離:** S3 キーは `users/{userId}/` プレフィックス — ユーザー間アクセス不可
- **最小権限:** 各 Lambda/ECS タスクに専用 IAM ロール（最小限の権限）
- **パーミッションバウンダリ:** 全ロールに `MZJTeamBoundary` 適用
- **ネットワーク:** ECS コンテナはプライベートサブネット（パブリック IP なし）、外部通信は NAT 経由のみ
- **コンテンツ安全性:** Bedrock Guardrails が AI 出力をフィルタ

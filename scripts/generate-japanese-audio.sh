#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Generate Japanese meeting audio for multi-language testing
# Two speakers discussing a sprint review
# ---------------------------------------------------------------------------

set -euo pipefail

AWS_PROFILE="terraform"
AWS_REGION="ap-northeast-1"
OUTPUT_DIR="docs/Testing"

echo "=============================================="
echo "  Generating Japanese Meeting Audio"
echo "=============================================="
echo ""

# Speaker 1 - Kazuha (female, project manager)
# Speaker 2 - Takumi (male, engineer)

# Segment 1 - Kazuha opens the meeting
SEG1="皆さん、おはようございます。今週のスプリントレビューを始めましょう。まず、田中さんから開発の進捗を報告してください。"

# Segment 2 - Takumi reports progress
SEG2="はい。今週はユーザー認証機能の実装を完了しました。ログインとサインアップのフローは全てテスト済みです。ただし、パスワードリセット機能にバグが一つ残っています。明日までに修正する予定です。"

# Segment 3 - Kazuha asks about API
SEG3="ありがとうございます。APIのパフォーマンスについてはどうですか？先週のレビューで、レスポンスタイムが遅いという問題がありましたよね。"

# Segment 4 - Takumi explains the fix
SEG4="はい、その件ですが、データベースのクエリを最適化しました。レスポンスタイムは平均200ミリ秒から50ミリ秒に改善されました。キャッシュレイヤーも追加したので、負荷テストでも問題ありません。"

# Segment 5 - Kazuha discusses next sprint
SEG5="素晴らしいですね。来週のスプリントでは、決済機能の実装を優先したいと思います。田中さん、水曜日までに技術設計書を作成してもらえますか？"

# Segment 6 - Takumi confirms and raises a concern
SEG6="承知しました。水曜日までに設計書を準備します。一つ確認ですが、決済プロバイダーはストライプを使う方針で合っていますか？セキュリティ審査が必要になるかもしれません。"

# Segment 7 - Kazuha wraps up
SEG7="はい、ストライプで進めます。セキュリティ審査については、私から法務チームに確認します。金曜日までに回答をもらえるようにします。他に質問はありますか？なければ、今日のミーティングは以上です。お疲れ様でした。"

echo "==> Generating speech segments..."

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Kazuha --output-format mp3 \
  --text "$SEG1" "$OUTPUT_DIR/jp_seg1.mp3" > /dev/null
echo "    ✓ Segment 1 (Kazuha)"

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Takumi --output-format mp3 \
  --text "$SEG2" "$OUTPUT_DIR/jp_seg2.mp3" > /dev/null
echo "    ✓ Segment 2 (Takumi)"

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Kazuha --output-format mp3 \
  --text "$SEG3" "$OUTPUT_DIR/jp_seg3.mp3" > /dev/null
echo "    ✓ Segment 3 (Kazuha)"

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Takumi --output-format mp3 \
  --text "$SEG4" "$OUTPUT_DIR/jp_seg4.mp3" > /dev/null
echo "    ✓ Segment 4 (Takumi)"

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Kazuha --output-format mp3 \
  --text "$SEG5" "$OUTPUT_DIR/jp_seg5.mp3" > /dev/null
echo "    ✓ Segment 5 (Kazuha)"

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Takumi --output-format mp3 \
  --text "$SEG6" "$OUTPUT_DIR/jp_seg6.mp3" > /dev/null
echo "    ✓ Segment 6 (Takumi)"

aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --voice-id Kazuha --output-format mp3 \
  --text "$SEG7" "$OUTPUT_DIR/jp_seg7.mp3" > /dev/null
echo "    ✓ Segment 7 (Kazuha)"

# Generate silence gap
aws polly synthesize-speech --profile "$AWS_PROFILE" --region "$AWS_REGION" \
  --engine neural --text-type ssml --voice-id Kazuha --output-format mp3 \
  --text '<speak><break time="2s"/></speak>' "$OUTPUT_DIR/jp_silence.mp3" > /dev/null

echo ""
echo "==> Concatenating..."

cat "$OUTPUT_DIR/jp_seg1.mp3" "$OUTPUT_DIR/jp_silence.mp3" \
    "$OUTPUT_DIR/jp_seg2.mp3" "$OUTPUT_DIR/jp_silence.mp3" \
    "$OUTPUT_DIR/jp_seg3.mp3" "$OUTPUT_DIR/jp_silence.mp3" \
    "$OUTPUT_DIR/jp_seg4.mp3" "$OUTPUT_DIR/jp_silence.mp3" \
    "$OUTPUT_DIR/jp_seg5.mp3" "$OUTPUT_DIR/jp_silence.mp3" \
    "$OUTPUT_DIR/jp_seg6.mp3" "$OUTPUT_DIR/jp_silence.mp3" \
    "$OUTPUT_DIR/jp_seg7.mp3" \
    > "$OUTPUT_DIR/test-japanese-sprint-review.mp3"

# Cleanup
rm -f "$OUTPUT_DIR"/jp_seg*.mp3 "$OUTPUT_DIR"/jp_silence.mp3

echo ""
echo "✓ Generated: $OUTPUT_DIR/test-japanese-sprint-review.mp3"
echo ""
echo "Content: Sprint review meeting in Japanese"
echo "Speakers: Kazuha (PM), Takumi (Engineer)"
echo "Topics: Auth feature complete, API performance fix, payment integration next sprint"
echo ""

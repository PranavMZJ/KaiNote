export type Locale = "en" | "ja";

export const translations = {
  // Navbar
  "nav.capture": { en: "Capture", ja: "キャプチャ" },
  "nav.meetings": { en: "Meetings", ja: "会議一覧" },
  "nav.signOut": { en: "Sign Out", ja: "ログアウト" },
  "nav.signIn": { en: "Sign In", ja: "ログイン" },
  "nav.getStarted": { en: "Get Started", ja: "始める" },

  // Home page
  "home.hero.title1": { en: "Voice to Minutes,", ja: "音声から議事録へ、" },
  "home.hero.title2": { en: "Instantly.", ja: "瞬時に。" },
  "home.hero.subtitle": {
    en: "Capture meetings, get real-time transcription with live translation, and let AI generate structured reports with action items — automatically.",
    ja: "会議を録音し、リアルタイム文字起こしとライブ翻訳を取得。AIが構造化されたレポートとアクションアイテムを自動生成します。",
  },
  "home.cta.start": { en: "Get Started Free", ja: "無料で始める" },
  "home.cta.signIn": { en: "Sign In", ja: "ログイン" },
  "home.features.title": { en: "Everything you need from a meeting", ja: "会議に必要なすべて" },
  "home.features.transcription.title": { en: "Live Transcription", ja: "ライブ文字起こし" },
  "home.features.transcription.desc": {
    en: "Real-time speech-to-text with speaker identification. See who said what as the meeting happens.",
    ja: "話者識別付きリアルタイム音声テキスト変換。会議中に誰が何を言ったかを確認。",
  },
  "home.features.translation.title": { en: "Live Translation", ja: "ライブ翻訳" },
  "home.features.translation.desc": {
    en: "Translate transcription to 7 languages in real-time. Switch languages mid-meeting with one click.",
    ja: "7言語へのリアルタイム翻訳。ワンクリックで会議中に言語を切り替え。",
  },
  "home.features.reports.title": { en: "AI-Powered Reports", ja: "AI レポート生成" },
  "home.features.reports.desc": {
    en: "Bedrock generates structured minutes: summary, decisions, action items with owners and deadlines.",
    ja: "Bedrockが構造化議事録を生成：要約、決定事項、担当者と期限付きアクションアイテム。",
  },
  "home.features.followups.title": { en: "Smart Follow-Ups", ja: "スマートフォローアップ" },
  "home.features.followups.desc": {
    en: "AI agent detects overdue items from past meetings, sends notifications, and suggests follow-up meetings.",
    ja: "AIエージェントが過去の会議から期限超過アイテムを検出し、通知を送信、フォローアップ会議を提案。",
  },
  "home.features.rag.title": { en: "Meeting Context (RAG)", ja: "会議コンテキスト (RAG)" },
  "home.features.rag.desc": {
    en: "Each report references decisions and action items from your recent meetings for continuity.",
    ja: "各レポートは直近の会議の決定事項とアクションアイテムを参照し、継続性を確保。",
  },
  "home.features.notifications.title": { en: "Email Notifications", ja: "メール通知" },
  "home.features.notifications.desc": {
    en: "Action item owners receive email notifications with task details, deadlines, and meeting context.",
    ja: "アクションアイテムの担当者にタスク詳細、期限、会議コンテキスト付きのメール通知を送信。",
  },
  "home.howItWorks.title": { en: "How it works", ja: "使い方" },
  "home.howItWorks.step1.title": { en: "Start Capture", ja: "キャプチャ開始" },
  "home.howItWorks.step1.desc": {
    en: "Click one button. Select your audio language. KaiNote captures from your microphone.",
    ja: "ボタンを1つクリック。音声言語を選択。KaiNoteがマイクからキャプチャ。",
  },
  "home.howItWorks.step2.title": { en: "Live Transcription", ja: "ライブ文字起こし" },
  "home.howItWorks.step2.desc": {
    en: "See real-time text with speaker labels. Switch display language anytime for live translation.",
    ja: "話者ラベル付きリアルタイムテキストを表示。いつでも表示言語を切り替えてライブ翻訳。",
  },
  "home.howItWorks.step3.title": { en: "AI Generates Report", ja: "AI がレポート生成" },
  "home.howItWorks.step3.desc": {
    en: "Stop the meeting. AI analyzes the transcript and produces structured minutes in seconds.",
    ja: "会議を停止。AIがトランスクリプトを分析し、数秒で構造化議事録を生成。",
  },
  "home.howItWorks.step4.title": { en: "Automated Actions", ja: "自動アクション" },
  "home.howItWorks.step4.desc": {
    en: "Agent sends notifications, detects overdue items, and suggests follow-ups — all automatically.",
    ja: "エージェントが通知送信、期限超過検出、フォローアップ提案を自動実行。",
  },
  "home.poweredBy": { en: "Powered by", ja: "利用技術" },
  "home.footer": {
    en: "KaiNote — Built with ❤️ on AWS · Serverless · Secure · Multi-Language",
    ja: "KaiNote — AWS上に構築 ❤️ · サーバーレス · セキュア · 多言語対応",
  },

  // Capture page
  "capture.title": { en: "Meeting Capture", ja: "会議キャプチャ" },
  "capture.subtitle": {
    en: "Capture your meeting audio for AI-powered transcription and minutes generation.",
    ja: "会議音声をキャプチャし、AI文字起こしと議事録生成を行います。",
  },
  "capture.audioLanguage": { en: "Audio Language", ja: "音声言語" },
  "capture.displayLanguage": { en: "Display Transcription In", ja: "文字起こし表示言語" },
  "capture.sameAsAudio": { en: "Same as audio", ja: "音声と同じ" },
  "capture.start": { en: "Start Meeting Capture", ja: "会議キャプチャ開始" },
  "capture.stop": { en: "Stop and Generate Minutes", ja: "停止して議事録生成" },
  "capture.processing": { en: "Generating meeting minutes…", ja: "議事録を生成中…" },
  "capture.copy": { en: "Copy", ja: "コピー" },

  // Meetings page
  "meetings.title": { en: "Your Meetings", ja: "会議一覧" },
  "meetings.newCapture": { en: "+ New Capture", ja: "+ 新規キャプチャ" },
  "meetings.search": { en: "Search meetings...", ja: "会議を検索..." },
  "meetings.all": { en: "All", ja: "すべて" },
  "meetings.completed": { en: "Completed", ja: "完了" },
  "meetings.processing": { en: "Processing", ja: "処理中" },
  "meetings.failed": { en: "Failed", ja: "失敗" },
  "meetings.pending": { en: "Pending", ja: "保留中" },
  "meetings.newest": { en: "↓ Newest", ja: "↓ 新しい順" },
  "meetings.oldest": { en: "↑ Oldest", ja: "↑ 古い順" },
  "meetings.noResults": { en: "No meetings match your filter.", ja: "フィルターに一致する会議がありません。" },
  "meetings.empty.title": { en: "No meetings yet", ja: "会議がまだありません" },
  "meetings.empty.desc": {
    en: "Start your first meeting capture to generate AI-powered minutes.",
    ja: "最初の会議キャプチャを開始して、AI議事録を生成しましょう。",
  },
  "meetings.empty.cta": { en: "Start Meeting Capture", ja: "会議キャプチャ開始" },
  "meetings.close": { en: "✕ Close", ja: "✕ 閉じる" },
  "meetings.downloadReport": { en: "📥 Download Report", ja: "📥 レポートDL" },
  "meetings.share": { en: "🔗 Share", ja: "🔗 共有" },
  "meetings.delete": { en: "🗑️ Delete", ja: "🗑️ 削除" },
  "meetings.deleteConfirm.title": { en: "Delete Meeting?", ja: "会議を削除しますか？" },
  "meetings.deleteConfirm.desc": {
    en: "This will permanently delete the meeting, its transcript, report, and all associated data. This action cannot be undone.",
    ja: "会議、トランスクリプト、レポート、関連データがすべて完全に削除されます。この操作は元に戻せません。",
  },
  "meetings.deleteConfirm.cancel": { en: "Cancel", ja: "キャンセル" },
  "meetings.deleteConfirm.confirm": { en: "Delete", ja: "削除" },
  "meetings.deleting": { en: "Deleting...", ja: "削除中..." },
  "meetings.retry": { en: "Retry", ja: "再試行" },
} as const;

export type TranslationKey = keyof typeof translations;

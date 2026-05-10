<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/svg/kainote-logo-dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="docs/images/svg/kainote-logo-light.svg">
  <img alt="KaiNote" src="docs/images/svg/kainote-logo-light.svg" width="320">
</picture>

<br/><br/>

### AI-Powered Meeting Minutes — From Voice to Structured Reports in Seconds

<br/>

**English** · [日本語](./README.md) · [Architecture](./infra/architecture_en.md) · [Deployment Guide](./infra/README_en.md)

</div>

<hr/>

<div align="center">
  <img src="docs/gif/kainote-demo.gif" alt="KaiNote Demo" width="800">
</div>

<br/>

**KaiNote** (会Note) is a production-ready meeting minutes SaaS application built entirely on AWS. It captures live meeting audio from the browser, transcribes it in real-time with live translation, and automatically generates structured reports using Amazon Bedrock. A post-meeting AI agent handles notifications, overdue detection, and follow-up suggestions — all autonomously.

<br/>

## ✨ Key Features

- 🎙️ **Live Transcription** — Real-time speech-to-text with speaker identification via Amazon Transcribe Streaming
- 🌐 **Live Translation** — Translate transcription to 7 languages in real-time, switchable mid-session
- 🤖 **AI Minutes Generation** — Bedrock (Claude Haiku 4.5) produces structured reports: summary, decisions, action items, risks
- 🔗 **RAG (Prior Meeting Context)** — Each report references decisions and action items from recent meetings
- 📋 **Post-Meeting Agent** — Automatically sends notifications, detects overdue items, suggests follow-up meetings
- 📧 **Email Notifications** — Action item owners receive email with task details, deadlines, and context
- 🗣️ **Speaker Re-Attribution** — Bedrock analyzes transcript to identify speakers by name from conversation context
- ✏️ **Inline Editing** — Edit any field in the generated report directly in the browser
- 🌙 **Dark / Light Theme** — Toggle between themes with one click
- 🇯🇵 **Multi-Language UI** — Switch app interface between English and Japanese
- 🔍 **Search & Filter** — Find meetings by title, date, or status
- 🔒 **Secure** — Cognito auth, per-user data isolation, least-privilege IAM, Bedrock Guardrails

<br/>

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React / Next.js, S3 + CloudFront |
| Auth | Amazon Cognito |
| API | API Gateway (REST + WebSocket) |
| Live Transcription | ECS EC2 (t3.micro) + ALB + Transcribe Streaming |
| Translation | Amazon Translate |
| AI | Amazon Bedrock (Claude Haiku 4.5) + Guardrails |
| Orchestration | AWS Step Functions |
| Backend | AWS Lambda (Python 3.12) × 10 |
| Storage | Amazon S3, DynamoDB |
| Notifications | Amazon SNS |
| Networking | VPC, ALB, NAT Gateway |
| IaC | Terraform (~130 resources) |

<br/>

## 🚀 Getting Started

> Full deployment guide: **[infra/README_en.md](./infra/README_en.md)**

```bash
cd infra && terraform init && terraform apply
./scripts/deploy-lambdas.sh
./scripts/deploy-transcription-service.sh
./scripts/deploy-frontend.sh
```

<br/>

## 📐 Architecture

> Full architecture documentation: **[infra/architecture_en.md](./infra/architecture_en.md)**

```
Browser → CloudFront → ALB → ECS EC2 → Transcribe Streaming
                                      → Amazon Translate (live)
                                      → Bedrock (speaker re-attribution)
                                      → S3 → Step Functions
                                              → Cleanup → Chunker → Generator (Bedrock + RAG)
                                              → Validator → Store → Agent (Bedrock + SNS → Email)
```

<br/>

## 📂 Project Structure

```
├── backend/lambdas/       10 Lambda handlers (API, Generator, Agent, etc.)
├── services/transcription/ ECS container (Transcribe + Translate + Bedrock)
├── frontend/src/           React/Next.js app (dark theme, i18n)
├── infra/                  Terraform (~20 .tf files, ~130 resources)
├── scripts/                Deploy scripts (lambdas, frontend, container)
└── docs/                   Architecture diagrams, test audio, GIF demo
```

<br/>

## 🏷️ Naming Conventions

| Convention | Value |
|-----------|-------|
| Resource naming | `Pranav-meeting-minutes-{purpose}` |
| Tags | `User=Pranav`, `Project=meeting-minutes` |
| Permissions boundary | `MZJTeamBoundary` |
| Region | `ap-northeast-1` |

<br/>

<div align="center">
  <sub>Built with ❤️ on AWS · Serverless · Secure · Multi-Language</sub>
</div>

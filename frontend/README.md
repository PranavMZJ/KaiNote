# KaiNote Frontend

React/Next.js single-page application for the KaiNote meeting minutes platform. Uses a Lusion-inspired dark theme with glassmorphism panels.

## Tech Stack

- **Framework:** Next.js 16 (static export mode for S3 hosting)
- **Auth:** Amazon Cognito (`amazon-cognito-identity-js`)
- **Audio:** Web Audio API (PCM 16-bit, 16kHz)
- **WebSocket:** Native WebSocket to ECS Fargate transcription service
- **Styling:** CSS custom properties (design system in `src/styles/`)

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page (KaiNote branding) |
| `/login` | Sign in with Cognito |
| `/register` | Create account + email verification |
| `/capture` | Meeting capture (audio + live transcription + translation) |
| `/meetings` | Meeting list + report viewer + agent actions |

## Environment Variables

Create `frontend/.env.local` (see `.env.local.example`):

```
NEXT_PUBLIC_COGNITO_USER_POOL_ID=ap-northeast-1_xxxxx
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=xxxxx
NEXT_PUBLIC_API_GATEWAY_URL=https://xxxxx.execute-api.ap-northeast-1.amazonaws.com/v1
NEXT_PUBLIC_WEBSOCKET_URL=wss://xxxxx.execute-api.ap-northeast-1.amazonaws.com/v1
NEXT_PUBLIC_TRANSCRIPTION_WS_URL=wss://xxxxx.cloudfront.net
```

Generate from Terraform outputs:
```bash
cat > .env.local << EOF
NEXT_PUBLIC_COGNITO_USER_POOL_ID=$(terraform -chdir=../infra output -raw cognito_user_pool_id)
NEXT_PUBLIC_COGNITO_APP_CLIENT_ID=$(terraform -chdir=../infra output -raw cognito_app_client_id)
NEXT_PUBLIC_API_GATEWAY_URL=$(terraform -chdir=../infra output -raw rest_api_endpoint)
NEXT_PUBLIC_WEBSOCKET_URL=$(terraform -chdir=../infra output -raw ws_api_endpoint)
NEXT_PUBLIC_TRANSCRIPTION_WS_URL=wss://$(terraform -chdir=../infra output -raw cloudfront_distribution_domain_name)
EOF
```

## Development

```bash
npm install
npm run dev       # http://localhost:3000
```

## Build & Deploy

```bash
npm run build     # Static export to out/
# Or use the deploy script:
../scripts/deploy-frontend.sh
```

## Key Components

| Component | File | Description |
|-----------|------|-------------|
| TranscriptPanel | `src/components/TranscriptPanel.tsx` | Live transcription display |
| ReportRenderer | `src/components/ReportRenderer.tsx` | Meeting report viewer |
| AgentActionsPanel | `src/components/AgentActionsPanel.tsx` | Post-meeting agent results |
| ExportControls | `src/components/ExportControls.tsx` | Copy/download buttons |
| TranscriptionClient | `src/capture/TranscriptionClient.ts` | WebSocket client to Fargate |
| AudioCapture | `src/capture/AudioCapture.ts` | Browser microphone capture |

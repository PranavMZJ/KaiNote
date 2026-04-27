# Implementation Plan: Meeting Minutes SaaS Application

## Overview

This plan implements a production-ready Meeting Minutes SaaS application on AWS. Development proceeds incrementally: Terraform infrastructure first, then Python Lambda backend functions, Step Functions orchestration, and finally the React/Next.js frontend. Each task builds on previous work so there is no orphaned code. Property-based tests (Hypothesis for Python, fast-check for TypeScript) and unit tests are placed close to the code they validate.

## Tasks

- [x] 1. Set up project structure and shared configuration
  - Create top-level directory structure: `infra/` (Terraform), `backend/` (Python Lambdas), `frontend/` (React/Next.js), `tests/` (unit + property tests)
  - Create `infra/provider.tf` with AWS provider (`ap-northeast-1`, profile `terraform`)
  - Create `infra/locals.tf` with `common_tags` (`User=Pranav`, `Project=meeting-minutes`) and `permissions_boundary` ARN (`arn:aws:iam::681561127010:policy/MZJTeamBoundary`)
  - Create `infra/variables.tf` with shared variables (region, project name, user name)
  - Create `backend/requirements.txt` with shared Python dependencies (boto3, jsonschema, tiktoken or equivalent tokenizer)
  - Create `tests/requirements.txt` with test dependencies (pytest, hypothesis, moto)
  - _Requirements: 16.1, 16.2, 16.3, 16.4_

- [x] 2. Provision authentication and API infrastructure (Terraform)
  - [x] 2.1 Create Cognito User Pool and App Client
    - Create `infra/cognito.tf` with `Pranav-meeting-minutes-user-pool` and `Pranav-meeting-minutes-app-client`
    - Configure password policy (min 8 chars, require uppercase/lowercase/number/symbol), self-registration, email verification
    - Set token expiry: access token 1 hour, refresh token 30 days
    - Apply common tags and output User Pool ID, App Client ID, and JWKS endpoint
    - _Requirements: 1.1, 1.2, 16.1, 16.2_

  - [x] 2.2 Create REST API Gateway with Cognito Authorizer
    - Create `infra/api_gateway_rest.tf` with `Pranav-meeting-minutes-rest-api`
    - Configure Cognito authorizer `Pranav-meeting-minutes-cognito-auth`
    - Define resource paths: `/meetings`, `/meetings/{meetingId}`, `/meetings/{meetingId}/report`, `/meetings/{meetingId}/report/download`, `/meetings/{meetingId}/retry`
    - Enable CORS for frontend origin
    - Set throttling: 1000 burst, 500 sustained
    - Apply common tags
    - _Requirements: 1.3, 1.4, 13.2, 16.1, 16.2_

  - [x] 2.3 Create WebSocket API Gateway
    - Create `infra/api_gateway_ws.tf` with `Pranav-meeting-minutes-ws-api`
    - Define routes: `$connect`, `$disconnect`, `audio_chunk`, `stop_capture`
    - Configure connection idle timeout (10 minutes), message payload limit (128 KB)
    - Apply common tags
    - _Requirements: 2.5, 3.1, 16.1, 16.2_

- [x] 3. Provision storage and data infrastructure (Terraform)
  - [x] 3.1 Create S3 buckets
    - Create `infra/s3.tf` with `pranav-meeting-minutes-data` and `pranav-meeting-minutes-prompts` buckets
    - Enable SSE-S3 encryption, versioning on data bucket, block all public access
    - Configure lifecycle rule: transition to Glacier after 90 days on data bucket
    - Configure CORS on data bucket for frontend origin
    - Apply common tags
    - _Requirements: 5.4, 13.1, 15.4, 16.3_

  - [x] 3.2 Create DynamoDB connections table
    - Create `infra/dynamodb.tf` with `Pranav-meeting-minutes-connections` table
    - Partition key: `connectionId` (String), GSI on `userId`
    - Enable TTL on `ttl` attribute, on-demand capacity mode
    - Apply common tags
    - _Requirements: 15.1, 16.1, 16.2_

- [x] 4. Provision Lambda functions and IAM roles (Terraform)
  - [x] 4.1 Create IAM roles for all Lambda functions
    - Create `infra/iam.tf` with roles for: ws-auth, ws-handler, stream-bridge, api, cleanup, chunker, generator, validator, store
    - Every role uses `Pranav-meeting-minutes-{purpose}-role` naming and `MZJTeamBoundary` permissions boundary
    - Attach least-privilege policies: each role gets only the permissions its Lambda needs (S3 read/write for specific prefixes, DynamoDB access, Transcribe streaming, Bedrock invoke, Step Functions start, CloudWatch logs)
    - Apply common tags to all roles
    - _Requirements: 13.4, 13.5, 16.1, 16.2_

  - [x] 4.2 Create Lambda function resources
    - Create `infra/lambda.tf` with all Lambda functions: `Pranav-meeting-minutes-ws-authorizer`, `Pranav-meeting-minutes-ws-handler`, `Pranav-meeting-minutes-stream-bridge`, `Pranav-meeting-minutes-api`, `Pranav-meeting-minutes-cleanup`, `Pranav-meeting-minutes-chunker`, `Pranav-meeting-minutes-generator`, `Pranav-meeting-minutes-validator`, `Pranav-meeting-minutes-store`
    - Configure runtimes (Python 3.12), memory, timeouts per design (stream-bridge: 512MB/900s, generator: 1024MB/120s, others: 256MB/30s)
    - Set environment variables per design (TRANSCRIPT_BUCKET, STEP_FUNCTION_ARN, PROMPT_BUCKET, PROMPT_VERSION, GUARDRAIL_ID, GUARDRAIL_VERSION, MODEL_ID)
    - Wire Lambda integrations to API Gateway REST and WebSocket routes
    - Create CloudWatch log groups `Pranav-meeting-minutes-{component}-logs`
    - Apply common tags
    - _Requirements: 14.1, 14.2, 14.3, 16.1, 16.2_

- [ ] 5. Provision Step Functions and Bedrock Guardrail (Terraform)
  - [x] 5.1 Create Step Functions state machine
    - Create `infra/step_functions.tf` with `Pranav-meeting-minutes-workflow` (Standard type)
    - Define state machine ASL: LoadTranscript → CleanTranscript → CheckTokenCount → (ChunkTranscript | GenerateMinutes) → ValidateSchema → (StoreReport | RetryGeneration) → UpdateStatus
    - Configure retry blocks on each Lambda task (IntervalSeconds: 2, MaxAttempts: 2, BackoffRate: 2.0, JitterStrategy: FULL)
    - Configure Catch blocks transitioning to MarkFailed state
    - Create IAM role `Pranav-meeting-minutes-sfn-role` with MZJTeamBoundary and permissions to invoke all workflow Lambdas
    - Create CloudWatch log group for workflow execution logs
    - Apply common tags
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 13.4, 16.1, 16.2_

  - [x] 5.2 Create Bedrock Guardrail
    - Create `infra/bedrock.tf` with `Pranav-meeting-minutes-guardrail`
    - Configure content filter: block hate, insults, sexual, violence at HIGH threshold
    - Configure sensitive information filter: mask PII (SSN, credit card numbers)
    - Apply common tags
    - _Requirements: 7.2_

- [x] 6. Provision frontend hosting infrastructure (Terraform)
  - Create `infra/frontend.tf` with S3 bucket for static site hosting and CloudFront distribution
  - S3 bucket: `pranav-meeting-minutes-frontend` with block public access, SSE-S3
  - CloudFront distribution: OAC to S3, HTTPS only, default root object `index.html`, custom error response for SPA routing (403/404 → /index.html)
  - Apply common tags
  - _Requirements: 16.1, 16.3_

- [x] 7. Checkpoint — Validate Terraform infrastructure
  - Run `terraform init` and `terraform validate` in `infra/` to verify all configurations are syntactically correct
  - Run `terraform plan` to verify resource creation plan
  - Ensure all resources follow naming convention `Pranav-meeting-minutes-{purpose}`, all IAM roles have MZJTeamBoundary, and all resources have required tags
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement data models and shared utilities (Python backend)
  - [x] 8.1 Create data models and S3 key generation
    - Create `backend/models/transcript.py` with `RawTranscript`, `CleanedTranscript`, `TranscriptSegment` dataclasses matching the design data models
    - Create `backend/models/minutes.py` with `MinutesReport`, `Decision`, `ActionItem` dataclasses matching the Minutes Schema
    - Create `backend/models/meeting_status.py` with `MeetingStatus` dataclass (meetingId, userId, status enum, timestamps, keys)
    - Create `backend/utils/s3_keys.py` with functions to generate user-scoped S3 key prefixes: `transcript_key(user_id, meeting_id)`, `report_key(user_id, meeting_id)`, `status_key(meeting_id)`
    - Implement JSON serialization/deserialization methods on all models
    - _Requirements: 5.4, 13.1, 15.4, 17.1, 17.2_

  - [ ]* 8.2 Write property test: Minutes Report Serialization Round-Trip (Property 1)
    - **Property 1: Minutes Report Serialization Round-Trip**
    - Create `tests/unit/test_serialization.py`
    - Use Hypothesis to generate arbitrary valid MinutesReport objects (valid schema_version, participants, decisions with rationale/evidence, action items with confidence in [0.0, 1.0] and valid priority enum)
    - Assert: `parse(serialize(report)) == report` for all generated reports
    - **Validates: Requirements 17.1, 17.2, 17.3**

  - [ ]* 8.3 Write property test: User-Scoped S3 Key Isolation (Property 6)
    - **Property 6: User-Scoped S3 Key Isolation**
    - Create `tests/unit/test_s3_keys.py`
    - Use Hypothesis to generate pairs of distinct user IDs and arbitrary meeting IDs
    - Assert: generated S3 key prefixes for two different users have no common prefix below `users/`
    - **Validates: Requirements 13.1, 15.4**

- [ ] 9. Implement transcript cleanup Lambda
  - [x] 9.1 Create transcript cleanup function
    - Create `backend/lambdas/cleanup/handler.py` implementing the `Pranav-meeting-minutes-cleanup` Lambda
    - Load raw transcript JSON from S3, parse into `RawTranscript` model
    - Remove filler words, normalize formatting, merge adjacent segments from same speaker
    - Produce `CleanedTranscript` with `totalTokenCount` calculated
    - Store cleaned transcript to S3 at `users/{user_id}/transcripts/{meeting_id}/cleaned.json`
    - Log cleanup metrics (segments before/after, token count) to CloudWatch
    - Handle malformed JSON with descriptive error logging
    - _Requirements: 6.2, 14.1, 17.1, 17.4_

  - [ ]* 9.2 Write property test: Transcript Cleanup Preserves Meaningful Content (Property 5)
    - **Property 5: Transcript Cleanup Preserves Meaningful Content**
    - Create `tests/unit/test_cleanup.py`
    - Use Hypothesis to generate raw transcripts with a mix of meaningful speech segments and filler words
    - Assert: (a) all meaningful (non-filler) words are preserved in the cleaned output, (b) segment ordering is maintained
    - **Validates: Requirements 6.2**

  - [ ]* 9.3 Write unit tests for transcript cleanup
    - Test specific edge cases: empty transcript, single-segment transcript, all-filler transcript, mixed Japanese/English content
    - Test malformed JSON input produces descriptive error
    - _Requirements: 6.2, 17.4_

- [ ] 10. Implement transcript chunker Lambda
  - [x] 10.1 Create transcript chunker function
    - Create `backend/lambdas/chunker/handler.py` implementing the `Pranav-meeting-minutes-chunker` Lambda
    - Accept cleaned transcript, check `totalTokenCount` against 10,000 token threshold
    - If over threshold, split segments into chunks that each fit within the Bedrock model's context window
    - Preserve segment boundaries (never split a segment across chunks)
    - Return list of chunk objects, each with its segments and token count
    - _Requirements: 6.3_

  - [ ]* 10.2 Write property test: Transcript Chunking Preserves Content and Respects Limits (Property 2)
    - **Property 2: Transcript Chunking Preserves Content and Respects Limits**
    - Create `tests/unit/test_chunker.py`
    - Use Hypothesis to generate cleaned transcripts with varying segment counts and token counts
    - Assert: (a) each chunk's token count ≤ context window limit, (b) concatenating all chunks' segments in order equals the original segments
    - **Validates: Requirements 6.3**

- [ ] 11. Implement minutes generator Lambda
  - [x] 11.1 Create minutes generator function
    - Create `backend/lambdas/generator/handler.py` implementing the `Pranav-meeting-minutes-generator` Lambda
    - Load prompt template from S3 (`prompts/v{version}/minutes_prompt.txt`)
    - Substitute template variables: `{transcript}`, `{schema_version}`, `{language}`
    - Invoke Bedrock (`anthropic.claude-3-haiku-20240307-v1:0`) with guardrail parameters (`guardrailIdentifier`, `guardrailVersion`)
    - Parse structured JSON response into `MinutesReport` model
    - Set `needs_human_review = true` for action items with `confidence < 0.7`
    - Set fields to `null` rather than guessing when owner/due_date cannot be determined
    - Log Bedrock invocation latency, token usage, and errors to CloudWatch
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 8.1, 8.2, 14.3, 14.4_

  - [ ]* 11.2 Write property test: Confidence-Based Human Review Flagging (Property 4)
    - **Property 4: Confidence-Based Human Review Flagging**
    - Create `tests/unit/test_generator.py`
    - Use Hypothesis to generate action items with arbitrary confidence scores in [0.0, 1.0]
    - Assert: if confidence < 0.7 then `needs_human_review` is `true`; if confidence ≥ 0.7 then `needs_human_review` is `false`
    - **Validates: Requirements 7.7**

  - [ ]* 11.3 Write unit tests for minutes generator
    - Test prompt template loading and variable substitution
    - Test Bedrock response parsing (valid JSON, malformed JSON, guardrail-blocked response)
    - Test null handling for owner and due_date fields
    - Use moto to mock S3 for prompt template reads
    - _Requirements: 7.1, 7.4, 7.5, 7.6, 14.4_

- [ ] 12. Implement schema validator Lambda
  - [x] 12.1 Create schema validator function
    - Create `backend/lambdas/validator/handler.py` implementing the `Pranav-meeting-minutes-validator` Lambda
    - Load Minutes Schema JSON from S3 (`schemas/v{version}/minutes_schema.json`)
    - Validate generated report JSON against schema using `jsonschema` library
    - Check required fields, data types, enum values (priority: low/medium/high), confidence in [0.0, 1.0]
    - Return validation result with specific error messages for debugging
    - _Requirements: 6.5, 8.3_

  - [ ]* 12.2 Write property test: Schema Validation Accepts Valid and Rejects Invalid Reports (Property 3)
    - **Property 3: Schema Validation Accepts Valid and Rejects Invalid Reports**
    - Create `tests/unit/test_validator.py`
    - Use Hypothesis to generate: (a) valid Minutes_Schema-compliant JSON objects → assert validator returns success, (b) invalid JSON objects (missing fields, wrong types, invalid enums, confidence outside [0.0, 1.0]) → assert validator returns failure with descriptive error
    - **Validates: Requirements 6.5**

- [ ] 13. Implement report storage Lambda
  - [x] 13.1 Create report storage function
    - Create `backend/lambdas/store/handler.py` implementing the `Pranav-meeting-minutes-store` Lambda
    - Store validated report JSON to S3 at `users/{user_id}/reports/{meeting_id}/minutes.json`
    - Update meeting status object at `meetings/{meeting_id}/status.json` to `completed`
    - _Requirements: 6.7, 14.5_

- [x] 14. Implement WebSocket authorizer Lambda
  - Create `backend/lambdas/ws_authorizer/handler.py` implementing the `Pranav-meeting-minutes-ws-authorizer` Lambda
  - Extract JWT token from WebSocket `$connect` query string parameter
  - Fetch Cognito JWKS public keys (with caching)
  - Verify JWT signature, expiry, and issuer
  - Return IAM Allow/Deny policy document
  - _Requirements: 1.3, 1.4, 3.5, 13.2_

- [ ] 15. Implement WebSocket handler and streaming bridge Lambdas
  - [x] 15.1 Create WebSocket handler Lambda
    - Create `backend/lambdas/ws_handler/handler.py` implementing the `Pranav-meeting-minutes-ws-handler` Lambda
    - Handle `$connect`: store connection in DynamoDB (`connectionId`, `userId`, `meetingId`, `connectedAt`, `ttl`)
    - Handle `$disconnect`: remove connection from DynamoDB
    - Handle `audio_chunk`: forward audio data to streaming bridge Lambda
    - Handle `stop_capture`: signal streaming bridge to stop
    - _Requirements: 2.5, 2.6, 5.1, 5.2, 15.1_

  - [x] 15.2 Create streaming bridge Lambda
    - Create `backend/lambdas/stream_bridge/handler.py` implementing the `Pranav-meeting-minutes-stream-bridge` Lambda
    - Start Amazon Transcribe Streaming session (language: `ja-JP`, PCM 16-bit 16kHz, speaker diarization enabled, partial results enabled)
    - Receive audio chunks and forward to Transcribe Streaming
    - Receive transcript segments from Transcribe and forward back to client via WebSocket API Management API (`post_to_connection`)
    - On stop signal: end Transcribe session, collect final transcript, store raw transcript to S3
    - After storing transcript, start Step Functions execution with transcript S3 location
    - Log session start, stop, and error events to CloudWatch
    - _Requirements: 3.1, 3.2, 3.3, 4.6, 5.3, 5.4, 5.5, 5.6, 14.1_

  - [ ]* 15.3 Write unit tests for WebSocket handler
    - Test $connect stores connection in DynamoDB (moto)
    - Test $disconnect removes connection from DynamoDB (moto)
    - Test audio_chunk routing
    - _Requirements: 2.5, 15.1_

- [x] 16. Implement REST API Lambda
  - Create `backend/lambdas/api/handler.py` implementing the `Pranav-meeting-minutes-api` Lambda
  - `GET /meetings`: list user's meetings from S3 status objects, scoped by user ID from JWT
  - `GET /meetings/{meetingId}`: get meeting details and status
  - `GET /meetings/{meetingId}/report`: get generated report JSON from S3
  - `PUT /meetings/{meetingId}/report`: save edited report as `minutes_edited.json`, preserving original
  - `GET /meetings/{meetingId}/report/download`: generate pre-signed S3 URL for JSON download
  - `POST /meetings/{meetingId}/retry`: restart Step Functions execution for failed meetings
  - Extract user ID from JWT claims for all operations
  - _Requirements: 9.1, 10.4, 11.2, 12.4, 13.1, 13.3_

- [x] 17. Upload prompt template and schema files
  - Create `backend/prompts/v1/minutes_prompt.txt` with the prompt template including system instructions, output schema definition, few-shot examples, and template variables (`{transcript}`, `{schema_version}`, `{language}`)
  - Create `backend/schemas/v1/minutes_schema.json` with the full Minutes Schema from the design document
  - Include instructions in the prompt for setting `needs_human_review: true` when `confidence < 0.7` and setting fields to `null` rather than guessing
  - Create a deployment script or Terraform `aws_s3_object` resources to upload these to the `pranav-meeting-minutes-prompts` bucket under versioned paths
  - _Requirements: 7.1, 7.6, 7.7, 8.1, 8.2_

- [x] 18. Checkpoint — Validate backend Lambdas and workflow
  - Run `pytest tests/unit/` to execute all Python unit tests and property tests
  - Verify all Lambda handlers import correctly and have proper error handling
  - Verify Step Functions ASL definition references correct Lambda ARNs
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 19. Set up frontend project and authentication
  - [x] 19.1 Initialize React/Next.js project with design system
    - Create `frontend/` with Next.js (static export mode for S3 hosting)
    - Install dependencies: `amazon-cognito-identity-js` (or `@aws-amplify/auth`), `fast-check`, `@testing-library/react`, `jest`
    - Install `Inter` and `JetBrains Mono` fonts via `next/font`
    - Create `frontend/src/styles/globals.css` with all CSS custom properties from `.kiro/steering/design-system.md` (color palette, typography, spacing, border-radius, shadows, motion tokens)
    - Create `frontend/src/styles/components.css` with reusable utility classes: `.glass-panel`, `.elevated-card`, `.accent-glow`, `.recording-pulse`
    - Apply dark theme (`--bg-primary`) as the default background on `<body>`
    - Add `prefers-reduced-motion` media query to disable animations when user prefers reduced motion
    - Configure environment variables for Cognito User Pool ID, App Client ID, API Gateway endpoints, WebSocket URL
    - Follow the Lusion-inspired design system: dark theme, generous whitespace, minimal chrome, smooth transitions, glassmorphism panels
    - _Requirements: 1.5, 1.6_

  - [x] 19.2 Implement authentication flow
    - Create `frontend/src/auth/` module with Cognito login, registration, and token management
    - Store JWT in memory only (not localStorage)
    - Include JWT in Authorization header for all REST API requests
    - Include JWT as query parameter for WebSocket connections
    - Create login page: dark theme, centered card with glass-panel effect, accent-primary submit button, smooth fade-in animation
    - Create registration page: matching style, email verification step
    - _Requirements: 1.2, 1.5, 1.6_

- [ ] 20. Implement audio capture and WebSocket streaming (Frontend)
  - [x] 20.1 Create audio capture module
    - Create `frontend/src/capture/AudioCapture.ts` using Web Audio API / MediaRecorder API
    - Capture PCM 16-bit, 16kHz audio from microphone
    - Encode audio chunks as base64 for WebSocket transmission
    - _Requirements: 2.2, 2.3, 2.6_

  - [x] 20.2 Create WebSocket connection manager
    - Create `frontend/src/capture/WebSocketManager.ts` with connection lifecycle management
    - Connect to WebSocket API with JWT token in query parameter
    - Send `audio_chunk` messages with base64-encoded PCM data
    - Send `stop_capture` message on stop
    - Handle incoming `transcript_segment`, `capture_stopped`, `processing_complete`, `error`, `connection_warning` messages
    - Implement reconnection logic with exponential backoff (1s, 2s, 4s, max 3 attempts)
    - _Requirements: 2.5, 2.6, 3.3, 12.1, 12.2_

  - [x] 20.3 Create meeting capture page
    - Create `frontend/src/pages/MeetingCapture.tsx` with "Start Meeting Capture" and "Stop and Generate Minutes" buttons
    - "Start" button: accent-primary style with accent-glow on hover, bold text, large padding
    - "Stop" button: danger style (error border, error text), appears only during active capture
    - Show capture-active indicator: pulsing red dot (recording-pulse animation) + elapsed timer in font-mono, displayed in a sticky glass-panel header bar
    - Show connection-lost warning: glass-panel toast with warning color border, slide-in from top
    - Show error message if microphone access is denied: elevated-card with error styling
    - Page background: bg-primary with generous spacing (space-24 top padding)
    - _Requirements: 2.1, 2.4, 2.7, 5.1_

- [ ] 21. Implement live transcript panel (Frontend)
  - [x] 21.1 Create transcript preview component
    - Create `frontend/src/components/TranscriptPanel.tsx` displaying live transcript segments
    - Panel style: bg-primary background with left border (2px accent-primary)
    - Speaker labels: text-xs, uppercase, letter-spacing-wide, accent-primary color
    - Partial segments: text-tertiary, italic styling
    - Final segments: text-primary, normal weight
    - New segments slide in from bottom with fade-in animation (translateY(8px) → 0, duration-normal)
    - Auto-scroll to most recent caption with smooth scroll behavior
    - Append new segments within 2 seconds of receipt
    - Segments separated by space-3 gap
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 21.2 Write property test: Speaker Label Display in Transcript Segments (Property 8)
    - **Property 8: Speaker Label Display in Transcript Segments**
    - Create `tests/frontend/transcript.property.test.ts`
    - Use fast-check to generate transcript segments with non-empty speaker labels and text
    - Assert: the formatted display output contains both the speaker label and the segment text
    - **Validates: Requirements 4.2**

- [ ] 22. Implement report display and editing (Frontend)
  - [x] 22.1 Create report renderer component
    - Create `frontend/src/components/ReportRenderer.tsx` displaying structured meeting minutes
    - Sections separated by border-subtle dividers with space-12 vertical gap
    - Section headings: text-h2, text-primary, letter-spacing-tight
    - Decision cards: elevated-card with left border accent-primary, showing rationale, owner, and evidence snippet (evidence in bg-elevated, font-mono, text-small)
    - Action item cards: elevated-card, warning-colored border if needs_human_review is true, showing task, owner, due_date, priority, and confidence score
    - Confidence badge: small pill (radius-sm), green (success) if ≥0.7, orange (warning) if <0.7
    - Processing status: centered spinner with accent-primary color, status text below in text-secondary
    - Cards fade in with staggered animation on page load
    - Show processing status indicator while report is loading
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [ ]* 22.2 Write property test: Report Rendering Completeness (Property 7)
    - **Property 7: Report Rendering Completeness**
    - Create `tests/frontend/report.property.test.ts`
    - Use fast-check to generate valid decision objects and action item objects
    - Assert: rendered output contains decision text, rationale, evidence; action item task, priority, confidence; and when owner/due_date is non-null, they also appear
    - **Validates: Requirements 9.3, 9.4**

  - [x] 22.3 Implement inline editing and human review highlights
    - Add inline editing capability to all report fields in `ReportRenderer.tsx`
    - Editable fields: click-to-edit with subtle bg-elevated background on focus, border-focus ring
    - Visually highlight action items where `needs_human_review` is `true`: warning-colored left border + small warning icon badge
    - Visually highlight action items where `owner` is `null` or `due_date` is `null`: dashed border-subtle outline with "Missing" label in text-tertiary
    - Save button: accent-primary style, appears only when edits are pending
    - On save, call `PUT /meetings/{meetingId}/report` to store edited version while preserving original
    - Show save-success toast (glass-panel, slide-in from top, auto-dismiss after 3s)
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 23. Implement export and download (Frontend)
  - Create `frontend/src/components/ExportControls.tsx` with "Copy to Clipboard" and "Download JSON" buttons
  - Buttons: secondary style (transparent bg, border-subtle, text-primary), icon + text, side by side
  - "Copy to Clipboard" copies formatted meeting minutes as text from the currently displayed (potentially edited) version; show brief "Copied!" toast on success
  - "Download JSON" calls `GET /meetings/{meetingId}/report/download` for a pre-signed URL and triggers download
  - Handle export failures with glass-panel error notification and retry suggestion
  - _Requirements: 11.1, 11.2, 11.3_

- [x] 24. Implement meetings list and navigation (Frontend)
  - Create `frontend/src/pages/MeetingsList.tsx` listing user's meetings as elevated-card items
  - Each card shows meeting title, date, and status badge (pill-shaped, color-coded: text-secondary for pending, accent-primary for processing, success for completed, error for failed)
  - Cards have hover effect: border-focus, translateY(-2px), increased shadow
  - Navigate to report view on click for completed meetings
  - Show retry button (secondary style) for failed meetings calling `POST /meetings/{meetingId}/retry`
  - Handle network offline state: disable capture actions, show offline indicator (glass-panel banner at top)
  - Empty state: centered text-secondary message with large icon, "No meetings yet" + CTA button to start capture
  - _Requirements: 9.1, 12.4, 14.5_

- [x] 25. Checkpoint — Validate frontend components
  - Run `npm test` (or `npx jest --run`) in `frontend/` to execute all frontend unit tests and property tests
  - Verify all pages render correctly, authentication flow works, and WebSocket messages are handled
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 26. Integration wiring and final validation
  - [x] 26.1 Wire frontend to backend endpoints
    - Create `frontend/src/api/client.ts` with typed API client for all REST endpoints (GET/PUT meetings, reports, retry)
    - Configure base URL from environment variables
    - Add JWT Authorization header interceptor
    - Verify frontend → REST API → Lambda → S3 data flow
    - _Requirements: 1.5, 9.1, 13.2, 13.3_

  - [x] 26.2 Create frontend build and deployment configuration
    - Configure Next.js for static export (`output: 'export'`)
    - Create deployment script or Terraform provisioner to sync build output to S3 frontend bucket and invalidate CloudFront cache
    - _Requirements: 16.1_

  - [ ]* 26.3 Write integration tests
    - Test end-to-end audio capture flow with mocked Transcribe
    - Test post-processing workflow with mocked AWS services (moto/LocalStack)
    - Test authentication flow with mocked Cognito tokens
    - Test report retrieval with mocked S3 pre-signed URLs
    - _Requirements: 1.3, 3.1, 6.1, 9.1_

- [x] 27. Final checkpoint — Ensure all tests pass
  - Run all Python tests: `pytest tests/`
  - Run all frontend tests: `npm test` in `frontend/`
  - Verify Terraform validates: `terraform validate` in `infra/`
  - Confirm all requirements are covered by implementation
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at infrastructure, backend, and frontend stages
- Property tests (Hypothesis for Python, fast-check for TypeScript) validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All Terraform resources follow MZJ-IAM naming (`Pranav-meeting-minutes-{purpose}`), tagging (`User=Pranav`, `Project=meeting-minutes`), and permissions boundary (`MZJTeamBoundary`)
- All resources deploy to `ap-northeast-1` using the `terraform` provider profile

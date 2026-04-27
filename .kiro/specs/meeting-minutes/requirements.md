# Requirements Document

## Introduction

This document defines the requirements for a production-ready Meeting Minutes SaaS application hosted on AWS. The application enables users to capture live meeting audio from a web browser, transcribe the audio in near real-time using Amazon Transcribe Streaming, and automatically generate structured meeting-minutes reports using Amazon Bedrock. Post-processing is orchestrated by AWS Step Functions after the transcript is available. The system follows AWS Well-Architected Framework principles and operates under MZJ-IAM policies in the ap-northeast-1 region.

## Glossary

- **Frontend**: A React/Next.js single-page application hosted on AWS (Amplify or S3+CloudFront) that provides the user interface for meeting capture, transcript preview, report viewing, and export.
- **Audio_Capture_Module**: The browser-based component that uses the Web Audio API and MediaRecorder API to capture microphone or system audio from the user's device.
- **Streaming_Backend**: A WebSocket-based backend service (API Gateway WebSocket API + Lambda, or ECS/Fargate) that receives audio chunks from the Frontend and forwards them to Amazon Transcribe Streaming.
- **Transcription_Service**: The Amazon Transcribe Streaming integration that converts audio streams into timestamped text transcript segments in near real-time.
- **Transcript_Store**: Amazon S3 storage used to persist raw transcripts, processed transcripts, and final reports under user-scoped prefixes.
- **Post_Processing_Workflow**: An AWS Step Functions state machine that orchestrates transcript cleanup, chunking, metadata extraction, LLM invocation, validation, and report storage after a transcript is available.
- **Minutes_Generator**: AWS Lambda functions that invoke Amazon Bedrock (with Guardrails) to produce structured meeting-minutes JSON from transcript data.
- **Report_Renderer**: The Frontend component that displays the structured meeting-minutes JSON as a formatted, human-readable report with editing and export capabilities.
- **Auth_Service**: Amazon Cognito User Pool that handles user registration, login, and JWT token issuance for authenticated API access.
- **API_Gateway**: AWS API Gateway (REST and WebSocket) that exposes backend endpoints with Cognito Authorizer-based authentication.
- **Minutes_Schema**: The versioned JSON schema defining the structure of meeting-minutes output, including meeting_title, meeting_datetime, participants, summary, agenda_items, key_discussion_points, decisions, action_items, risks_blockers, open_questions, and follow_up_needed.
- **Confidence_Score**: A numeric value (0.0 to 1.0) assigned by the Minutes_Generator to each extracted action item indicating the certainty of the extraction.
- **Evidence_Snippet**: A short excerpt from the raw transcript that supports an extracted decision or action item.

## Requirements

### Requirement 1: User Authentication

**User Story:** As a user, I want to securely log in to the meeting-minutes application, so that my meetings and reports are private and associated with my account.

#### Acceptance Criteria

1. THE Auth_Service SHALL provide user registration and login via Amazon Cognito User Pool.
2. WHEN a user successfully authenticates, THE Auth_Service SHALL issue a JWT token containing the user's identity claims.
3. THE API_Gateway SHALL validate JWT tokens using a Cognito Authorizer on every API request.
4. WHEN a request arrives without a valid JWT token, THE API_Gateway SHALL reject the request with HTTP 401 status.
5. THE Frontend SHALL store the JWT token in memory and include it in the Authorization header of every API request.
6. THE Frontend SHALL NOT store or expose AWS credentials to the browser.

### Requirement 2: Start Meeting Capture

**User Story:** As a user, I want to start live audio capture from my browser, so that the application can record and transcribe my meeting.

#### Acceptance Criteria

1. THE Frontend SHALL display a "Start Meeting Capture" button on the meeting page.
2. WHEN the user clicks "Start Meeting Capture", THE Audio_Capture_Module SHALL request microphone access from the browser.
3. WHEN microphone access is granted, THE Audio_Capture_Module SHALL begin capturing audio using the Web Audio API or MediaRecorder API.
4. WHEN audio capture begins, THE Frontend SHALL display a visible capture-active indicator (e.g., recording icon, elapsed timer).
5. WHEN audio capture begins, THE Audio_Capture_Module SHALL establish a WebSocket connection to the Streaming_Backend.
6. WHILE audio capture is active, THE Audio_Capture_Module SHALL stream audio chunks to the Streaming_Backend over the WebSocket connection.
7. IF microphone access is denied by the browser, THEN THE Frontend SHALL display an error message explaining that microphone permission is required.

### Requirement 3: Audio Streaming to Transcription

**User Story:** As a user, I want my meeting audio to be transcribed in near real-time, so that I can see a live transcript during the meeting.

#### Acceptance Criteria

1. WHEN the Streaming_Backend receives audio chunks from the Frontend, THE Streaming_Backend SHALL forward the audio to the Transcription_Service (Amazon Transcribe Streaming).
2. WHILE a transcription session is active, THE Transcription_Service SHALL return timestamped transcript segments to the Streaming_Backend.
3. WHEN the Streaming_Backend receives transcript segments, THE Streaming_Backend SHALL forward the segments to the Frontend over the WebSocket connection.
4. WHILE a transcription session is active, THE Frontend SHALL display incoming transcript segments in a live transcript preview panel.
5. THE Streaming_Backend SHALL authenticate the WebSocket connection using the user's JWT token before accepting audio data.

### Requirement 4: Live Transcript Captions

**User Story:** As a user, I want to see real-time speaker-attributed captions during meeting capture, so that I can follow the conversation as it happens and verify the transcription is working.

#### Acceptance Criteria

1. WHILE audio capture is active, THE Frontend SHALL display a live transcript panel showing incoming transcript segments as captions.
2. WHEN the Transcription_Service returns a transcript segment with a speaker label, THE Frontend SHALL display the speaker label alongside the corresponding text.
3. WHILE audio capture is active, THE Frontend SHALL auto-scroll the live transcript panel to show the most recent caption.
4. WHEN a new transcript segment arrives, THE Frontend SHALL append the segment to the live transcript panel within 2 seconds of receipt.
5. THE Frontend SHALL visually distinguish partial (in-progress) transcript segments from finalized segments (e.g., using italic or dimmed styling for partial results).
6. WHILE audio capture is active, THE Streaming_Backend SHALL request speaker identification from the Transcription_Service where supported by the chosen configuration.

### Requirement 5: Stop Capture and Store Transcript

**User Story:** As a user, I want to stop the meeting capture and have the raw transcript saved, so that the transcript is preserved before any AI processing begins.

#### Acceptance Criteria

1. THE Frontend SHALL display a "Stop and Generate Minutes" button while audio capture is active.
2. WHEN the user clicks "Stop and Generate Minutes", THE Audio_Capture_Module SHALL stop audio capture and close the microphone stream.
3. WHEN audio capture stops, THE Streaming_Backend SHALL end the Transcription_Service session and collect the final transcript.
4. WHEN the final transcript is available, THE Streaming_Backend SHALL store the raw transcript in the Transcript_Store under a user-scoped prefix (e.g., `users/{user_id}/transcripts/{meeting_id}/raw.json`).
5. THE Streaming_Backend SHALL store the raw transcript in the Transcript_Store before triggering any post-processing.
6. WHEN the raw transcript is stored, THE Streaming_Backend SHALL trigger the Post_Processing_Workflow by starting a Step Functions execution with the transcript S3 location as input.

### Requirement 6: Post-Processing Workflow Orchestration

**User Story:** As a user, I want the system to automatically process my transcript into structured meeting minutes, so that I receive a complete report without manual effort.

#### Acceptance Criteria

1. WHEN the Post_Processing_Workflow is triggered, THE Post_Processing_Workflow SHALL load the raw transcript from the Transcript_Store.
2. THE Post_Processing_Workflow SHALL clean and normalize the transcript (remove filler words, fix formatting).
3. WHEN the transcript exceeds 10,000 tokens, THE Post_Processing_Workflow SHALL chunk the transcript into segments that fit within the Bedrock model's context window.
4. THE Post_Processing_Workflow SHALL invoke the Minutes_Generator to extract meeting metadata, summary, decisions, action items, open questions, and risks from the transcript.
5. THE Post_Processing_Workflow SHALL validate the generated output against the Minutes_Schema.
6. IF the generated output fails schema validation, THEN THE Post_Processing_Workflow SHALL retry the Minutes_Generator invocation up to 2 additional times.
7. WHEN a valid report is generated, THE Post_Processing_Workflow SHALL store the final report JSON in the Transcript_Store under a user-scoped prefix (e.g., `users/{user_id}/reports/{meeting_id}/minutes.json`).
8. THE Post_Processing_Workflow SHALL log the execution status of each step to Amazon CloudWatch.

### Requirement 7: AI-Powered Minutes Generation

**User Story:** As a user, I want the AI to extract decisions, action items, and key points from my transcript, so that I get a comprehensive and structured meeting summary.

#### Acceptance Criteria

1. THE Minutes_Generator SHALL invoke Amazon Bedrock with a versioned prompt template to generate meeting minutes.
2. THE Minutes_Generator SHALL apply Amazon Bedrock Guardrails during model invocation to filter unsafe or inappropriate content.
3. THE Minutes_Generator SHALL produce output conforming to the Minutes_Schema, including: meeting_title, meeting_datetime, participants, summary, agenda_items, key_discussion_points, decisions, action_items, risks_blockers, open_questions, and follow_up_needed.
4. WHEN the Minutes_Generator extracts a decision, THE Minutes_Generator SHALL include the rationale, owner (or null if unclear), Evidence_Snippet, and timestamp for that decision.
5. WHEN the Minutes_Generator extracts an action item, THE Minutes_Generator SHALL include the task description, owner (or null if unclear), due_date (or null if unspecified), priority, Evidence_Snippet, timestamp, Confidence_Score, and needs_human_review flag.
6. WHEN the owner or due_date of an action item cannot be determined from the transcript, THE Minutes_Generator SHALL set the field to null instead of guessing.
7. WHEN the Confidence_Score of an action item is below 0.7, THE Minutes_Generator SHALL set the needs_human_review flag to true.

### Requirement 8: Minutes Schema Versioning

**User Story:** As a developer, I want the output schema and prompt templates to be versioned, so that changes to the AI output format are tracked and backward-compatible.

#### Acceptance Criteria

1. THE Minutes_Generator SHALL read prompt templates from a versioned location in the Transcript_Store (e.g., `prompts/v{version}/minutes_prompt.txt`).
2. THE Minutes_Generator SHALL include a schema_version field in every generated report.
3. WHEN the Minutes_Schema is updated, THE Post_Processing_Workflow SHALL continue to accept reports generated under previous schema versions.

### Requirement 9: Report Display

**User Story:** As a user, I want to view the generated meeting minutes in a clean, readable format, so that I can review the meeting outcomes.

#### Acceptance Criteria

1. WHEN the Post_Processing_Workflow completes, THE Frontend SHALL display a processing-complete notification to the user.
2. THE Report_Renderer SHALL display the meeting minutes with clearly separated sections: summary, agenda items, key discussion points, decisions, action items, risks/blockers, and open questions.
3. THE Report_Renderer SHALL display each decision with its rationale, owner, and Evidence_Snippet.
4. THE Report_Renderer SHALL display each action item with its task, owner, due_date, priority, and Confidence_Score.
5. WHEN the Frontend is loading the report, THE Frontend SHALL display a processing status indicator showing the current workflow state.

### Requirement 10: Human Review and Editing

**User Story:** As a user, I want to review and edit the generated minutes before finalizing them, so that I can correct any AI errors and fill in missing information.

#### Acceptance Criteria

1. THE Report_Renderer SHALL allow the user to edit all fields of the generated meeting minutes inline.
2. THE Report_Renderer SHALL visually highlight action items where needs_human_review is true (e.g., with a warning icon or colored border).
3. THE Report_Renderer SHALL visually highlight action items where owner is null or due_date is null.
4. WHEN the user saves edits, THE Frontend SHALL store the updated report in the Transcript_Store, preserving the original AI-generated version.

### Requirement 11: Export and Download

**User Story:** As a user, I want to copy or download the meeting minutes, so that I can share them with my team.

#### Acceptance Criteria

1. THE Frontend SHALL provide a "Copy to Clipboard" button that copies the formatted meeting minutes as text.
2. THE Frontend SHALL provide a "Download JSON" button that downloads the raw structured JSON report.
3. WHEN the user clicks an export button, THE Frontend SHALL generate the export from the currently displayed (potentially edited) version of the minutes.

### Requirement 12: Network Resilience

**User Story:** As a user, I want the application to handle network interruptions gracefully, so that I do not lose my meeting transcript due to connectivity issues.

#### Acceptance Criteria

1. IF the WebSocket connection drops during audio capture, THEN THE Streaming_Backend SHALL buffer received transcript segments and attempt to reconnect.
2. IF the WebSocket connection drops during audio capture, THEN THE Frontend SHALL display a connection-lost warning to the user.
3. IF the Post_Processing_Workflow fails at any step, THEN THE Post_Processing_Workflow SHALL preserve the raw transcript in the Transcript_Store and record the failure in CloudWatch logs.
4. WHEN the Post_Processing_Workflow fails, THE Frontend SHALL display an error message and provide an option to retry minutes generation.

### Requirement 13: Security and Access Control

**User Story:** As a user, I want my meeting data to be secure and accessible only to me, so that confidential meeting content is protected.

#### Acceptance Criteria

1. THE Transcript_Store SHALL organize all objects under user-scoped prefixes so that each user's data is logically isolated.
2. THE API_Gateway SHALL enforce authentication on all endpoints that access user data.
3. THE Streaming_Backend SHALL use pre-signed S3 URLs when the Frontend needs to access stored files directly.
4. THE Post_Processing_Workflow SHALL execute with least-privilege IAM roles that have only the permissions required for each step.
5. WHILE the MZJ-IAM policy is active, every IAM role created for this application SHALL include the MZJTeamBoundary permissions boundary (arn:aws:iam::681561127010:policy/MZJTeamBoundary).

### Requirement 14: Observability and Logging

**User Story:** As a developer, I want comprehensive logging and monitoring, so that I can diagnose failures and track system performance.

#### Acceptance Criteria

1. THE Streaming_Backend SHALL log transcription session start, stop, and error events to Amazon CloudWatch.
2. THE Post_Processing_Workflow SHALL log the start time, end time, and status of each workflow step to Amazon CloudWatch.
3. THE Minutes_Generator SHALL log Bedrock invocation latency, token usage, and error responses to Amazon CloudWatch.
4. IF a Bedrock invocation fails, THEN THE Minutes_Generator SHALL log the error details including request ID and error message.
5. THE Post_Processing_Workflow SHALL store the execution status (pending, processing, completed, failed) for each meeting, accessible by the Frontend.

### Requirement 15: Scalability and Multi-User Support

**User Story:** As a product owner, I want the system to support multiple concurrent users, so that the application can serve a growing user base.

#### Acceptance Criteria

1. THE Streaming_Backend SHALL handle multiple concurrent WebSocket connections from different users.
2. THE Post_Processing_Workflow SHALL support multiple concurrent Step Functions executions.
3. THE system SHALL use serverless components (Lambda, API Gateway, Step Functions, S3) to scale automatically with demand.
4. THE Transcript_Store SHALL use user-scoped prefixes to prevent data collision between concurrent users.

### Requirement 16: Resource Naming and Tagging

**User Story:** As a developer operating under MZJ-IAM policies, I want all AWS resources to follow the required naming and tagging conventions, so that resources pass IAM policy validation and are properly organized.

#### Acceptance Criteria

1. THE system SHALL tag every AWS resource with User=Pranav and Project=meeting-minutes.
2. THE system SHALL name AWS resources following the pattern Pranav-meeting-minutes-{purpose}.
3. THE system SHALL name S3 buckets following the pattern pranav-meeting-minutes-{purpose} (lowercase).
4. THE system SHALL deploy all resources in the ap-northeast-1 region using the terraform provider profile.

### Requirement 17: Transcript Parsing and Report Serialization

**User Story:** As a developer, I want reliable parsing of transcript data and serialization of report output, so that data integrity is maintained throughout the processing pipeline.

#### Acceptance Criteria

1. WHEN the Post_Processing_Workflow loads a raw transcript from S3, THE Post_Processing_Workflow SHALL parse the transcript JSON into an internal Transcript object.
2. THE Post_Processing_Workflow SHALL serialize the final Minutes_Schema-compliant report to JSON for storage.
3. FOR ALL valid Minutes_Schema-compliant report objects, serializing to JSON then parsing back SHALL produce an equivalent object (round-trip property).
4. IF the raw transcript JSON is malformed, THEN THE Post_Processing_Workflow SHALL log a descriptive error and mark the workflow execution as failed.

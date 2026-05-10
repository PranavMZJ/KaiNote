# Implementation Plan: Bedrock Agent for Post-Meeting Actions

## Overview

This plan implements the Bedrock Agent feature that autonomously takes post-meeting actions (notifications, overdue detection, follow-up suggestions) after meeting minutes are generated. Implementation proceeds: Terraform infrastructure first, then Lambda backend, Step Functions update, and finally frontend display.

## Prerequisites

Before starting, deploy the pending RAG changes:
1. `terraform apply` (IAM + DATA_BUCKET env var + prompt template)
2. `./scripts/deploy-lambdas.sh` (updated generator code)

## Tasks

- [ ] 1. Create SNS topic and agent prompt template
  - [ ] 1.1 Create SNS topic in Terraform
    - Create `infra/sns.tf` with `Pranav-meeting-minutes-notifications` topic
    - Enable server-side encryption (AWS managed key)
    - Add email subscription (configurable via variable)
    - Apply common tags (`User=Pranav`, `Project=meeting-minutes`)
    - Output the topic ARN
    - _Requirements: 2.1, 6.3, 7.2_

  - [ ] 1.2 Create agent prompt template
    - Create `backend/prompts/v1/agent_prompt.txt` with the structured prompt for Bedrock analysis
    - Prompt instructs Claude to: identify overdue items, suggest follow-ups, provide notification enhancements
    - Add S3 upload resource in `infra/s3_objects.tf`
    - _Requirements: 3.1, 3.5, 4.1_

- [ ] 2. Create Agent Lambda infrastructure (Terraform)
  - [ ] 2.1 Create IAM role for Agent Lambda
    - Add to `infra/iam.tf`: `Pranav-meeting-minutes-agent-role`
    - Permissions: S3 read (reports), S3 write (agent_actions), S3 list (user prefix), Bedrock InvokeModel, SNS Publish, CloudWatch Logs
    - Include MZJTeamBoundary permissions boundary
    - _Requirements: 6.1, 6.2, 6.4, 7.3_

  - [ ] 2.2 Create Agent Lambda function resource
    - Add to `infra/lambda.tf`: `Pranav-meeting-minutes-agent`
    - Runtime: Python 3.12, Memory: 1024 MB, Timeout: 120s
    - Environment variables: DATA_BUCKET, MODEL_ID, SNS_TOPIC_ARN, MEETINGS_TABLE
    - CloudWatch log group: `/aws/lambda/Pranav-meeting-minutes-agent`
    - Reference the existing Lambda layer (deps)
    - _Requirements: 7.1, 7.4, 7.5_

- [ ] 3. Update Step Functions workflow
  - [ ] 3.1 Add RunAgent state after StoreReport
    - Modify `infra/step_functions.tf` to add `RunAgent` state
    - RunAgent receives meetingId, userId, bucket, reportKey
    - Catch block transitions to UpdateStatus (not MarkFailed)
    - Retry: 1 attempt with 2s interval
    - StoreReport → RunAgent → UpdateStatus
    - _Requirements: 1.1, 1.2, 1.5_

  - [ ] 3.2 Update Step Functions IAM role
    - Add permission for SFN role to invoke the agent Lambda
    - _Requirements: 6.1_

- [ ] 4. Implement Agent Lambda handler
  - [ ] 4.1 Create agent handler with core logic
    - Create `backend/lambdas/agent/__init__.py` and `backend/lambdas/agent/handler.py`
    - Implement: load report from S3, load prior context (reuse RAG pattern from generator), invoke Bedrock with agent prompt, parse response
    - Handle Bedrock response parsing (strip code fences, validate JSON)
    - _Requirements: 1.3, 1.4, 3.1, 3.2, 3.5_

  - [ ] 4.2 Implement notification sending
    - Send SNS notifications for each action item with a non-null owner
    - Format subject line with priority prefix for high-priority items
    - Include task, owner, due_date, priority, evidence, and meeting context
    - Record all sent notifications in the agent report
    - Skip items where owner is null
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ] 4.3 Implement overdue detection and follow-up logic
    - Parse Bedrock analysis for overdue_items and follow_up_suggestion
    - Send overdue summary notification if overdue items detected
    - Send follow-up suggestion notification if recommended
    - Apply follow-up rules: follow_up_needed=true, 3+ open questions, overdue items, high-priority items without owners
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4_

  - [ ] 4.4 Store agent report to S3
    - Store `agent_actions.json` at `users/{user_id}/reports/{meeting_id}/agent_actions.json`
    - Include: notifications_sent, overdue_items, follow_up_suggestion, agent_execution_timestamp
    - _Requirements: 1.6, 5.1, 5.2_

- [ ] 5. Update REST API to serve agent report
  - [ ] 5.1 Add agent report endpoint to API Lambda
    - Update `backend/lambdas/api/handler.py` to handle `GET /meetings/{meetingId}/agent-report`
    - Load and return `agent_actions.json` from S3
    - Return empty object if file doesn't exist (agent hasn't run or failed)
    - _Requirements: 5.1, 5.3_

  - [ ] 5.2 Add API Gateway route
    - Add `/meetings/{meetingId}/agent-report` GET route to `infra/api_gateway_rest.tf`
    - Wire to existing API Lambda with Cognito authorizer
    - _Requirements: 5.3_

- [ ] 6. Update frontend to display agent actions
  - [ ] 6.1 Create AgentActionsPanel component
    - Create `frontend/src/components/AgentActionsPanel.tsx`
    - Display "🤖 Automated Actions" section with glass-panel styling
    - Sub-sections: Notifications Sent, Overdue Items (warning style), Follow-Up Suggestion
    - Hide section if no agent report available
    - _Requirements: 5.3, 5.4, 5.5, 5.6_

  - [ ] 6.2 Integrate into meeting report page
    - Update `frontend/src/app/meetings/[meetingId]/page.tsx` to fetch and display agent report
    - Add API client method for `GET /meetings/{meetingId}/agent-report`
    - Show loading state while fetching, gracefully handle missing report
    - _Requirements: 5.3_

- [ ] 7. Deploy and test
  - [ ] 7.1 Deploy infrastructure
    - Run `terraform apply` to create SNS topic, agent Lambda, updated Step Functions
    - Run `./scripts/deploy-lambdas.sh` to deploy agent Lambda code
    - Run `./scripts/deploy-frontend.sh` to deploy updated frontend
    - Subscribe an email to the SNS topic for testing

  - [ ] 7.2 End-to-end test
    - Record Meeting 1 → verify report generated, agent runs, notifications sent
    - Record Meeting 2 → verify overdue detection works against Meeting 1's action items
    - Verify agent_actions.json is stored and displayed in frontend
    - Verify meeting status remains "completed" even if agent fails

## Notes

- The agent uses the same Bedrock model as the generator (`jp.anthropic.claude-haiku-4-5-20251001-v1:0`)
- Agent failure is non-blocking — the meeting report is already stored before the agent runs
- SNS email subscription requires manual confirmation (one-time setup)
- Future enhancements: per-participant email routing, Slack/Teams integration, scheduled overdue checks

# Requirements Document: Bedrock Agent for Post-Meeting Actions

## Introduction

This document defines the requirements for a Bedrock Agent that autonomously performs post-meeting actions after meeting minutes are generated. The agent analyzes the generated report, cross-references prior meetings (via RAG), and takes actions: sending notifications to action item owners, detecting overdue items from past meetings, and suggesting follow-up meetings. The agent is triggered as a new Step Functions step after StoreReport completes.

## Glossary

- **Post_Meeting_Agent**: An Amazon Bedrock Agent that autonomously processes generated meeting minutes and takes follow-up actions.
- **Action_Notification**: An SNS notification sent to action item owners informing them of their assigned tasks, deadlines, and context.
- **Overdue_Detector**: Agent logic that compares current meeting action items against prior meeting action items to identify overdue or recurring unresolved items.
- **Follow_Up_Suggester**: Agent logic that determines whether a follow-up meeting is needed based on open questions, unresolved items, and meeting complexity.
- **Agent_Lambda**: A Lambda function that invokes the Bedrock Agent and processes its responses.
- **Notification_Topic**: An SNS topic used to deliver action item notifications to meeting participants.
- **Agent_Report**: A supplementary JSON document produced by the agent containing notifications sent, overdue items detected, and follow-up recommendations.

## Requirements

### Requirement 1: Agent Trigger and Orchestration

**User Story:** As a user, I want the system to automatically take follow-up actions after my meeting minutes are generated, so that action items are communicated and tracked without manual effort.

#### Acceptance Criteria

1. WHEN the StoreReport step completes successfully in the Post_Processing_Workflow, THE Post_Processing_Workflow SHALL invoke the Agent_Lambda as the next step.
2. THE Agent_Lambda SHALL receive the meetingId, userId, and reportKey as input from the Step Functions execution.
3. THE Agent_Lambda SHALL load the generated meeting report from S3 using the reportKey.
4. THE Agent_Lambda SHALL load prior meeting context (up to 3 most recent reports) using the same RAG mechanism as the Generator Lambda.
5. IF the Agent_Lambda fails, THE Post_Processing_Workflow SHALL NOT mark the overall meeting as failed — the meeting report remains valid and accessible.
6. THE Agent_Lambda SHALL store its results (Agent_Report) to S3 at `users/{user_id}/reports/{meeting_id}/agent_actions.json`.

### Requirement 2: Action Item Notifications

**User Story:** As a meeting participant, I want to receive notifications about action items assigned to me, so that I know what I need to do and by when.

#### Acceptance Criteria

1. FOR EACH action item in the generated report where owner is not null, THE Post_Meeting_Agent SHALL publish a notification to the Notification_Topic.
2. THE notification SHALL include: task description, owner name, due date (if available), priority, and meeting title for context.
3. THE notification SHALL include a brief context snippet from the meeting (the evidence field).
4. WHEN an action item has priority "high", THE notification subject SHALL be prefixed with "[HIGH PRIORITY]".
5. THE Post_Meeting_Agent SHALL NOT send notifications for action items where owner is null.
6. THE Agent_Report SHALL record all notifications sent (recipient, task, timestamp).

### Requirement 3: Overdue Item Detection

**User Story:** As a user, I want the system to detect when action items from previous meetings are overdue or being discussed again, so that I can track accountability.

#### Acceptance Criteria

1. THE Post_Meeting_Agent SHALL compare action items from the current meeting against action items from prior meetings (loaded via RAG).
2. WHEN a prior meeting action item's due_date has passed and the same topic appears in the current meeting, THE Post_Meeting_Agent SHALL flag it as "overdue/recurring".
3. WHEN overdue items are detected, THE Post_Meeting_Agent SHALL include them in the Agent_Report with: original task, original owner, original due date, and current meeting reference.
4. WHEN overdue items are detected, THE Post_Meeting_Agent SHALL publish a summary notification to the Notification_Topic highlighting the overdue items.
5. THE Post_Meeting_Agent SHALL use semantic similarity (via Bedrock) rather than exact string matching to identify recurring topics.

### Requirement 4: Follow-Up Meeting Suggestions

**User Story:** As a user, I want the system to suggest whether a follow-up meeting is needed, so that important discussions don't fall through the cracks.

#### Acceptance Criteria

1. THE Post_Meeting_Agent SHALL analyze the meeting report to determine if a follow-up meeting is recommended.
2. THE Post_Meeting_Agent SHALL recommend a follow-up when ANY of: (a) the report's `follow_up_needed` is true, (b) there are 3+ open questions, (c) there are overdue items from prior meetings, (d) there are high-priority action items without clear owners.
3. WHEN a follow-up is recommended, THE Agent_Report SHALL include: suggested topics, suggested participants, and recommended timeframe.
4. WHEN a follow-up is recommended, THE Post_Meeting_Agent SHALL publish a follow-up suggestion notification to the Notification_Topic.

### Requirement 5: Agent Report and Frontend Display

**User Story:** As a user, I want to see what automated actions the agent took after my meeting, so that I have visibility into notifications sent and issues detected.

#### Acceptance Criteria

1. THE Agent_Report SHALL be stored as JSON at `users/{user_id}/reports/{meeting_id}/agent_actions.json`.
2. THE Agent_Report SHALL include: notifications_sent (array), overdue_items (array), follow_up_suggestion (object or null), and agent_execution_timestamp.
3. THE Frontend SHALL display the Agent_Report as a supplementary section below the meeting minutes report.
4. THE Frontend SHALL show notifications sent with recipient and task.
5. THE Frontend SHALL show overdue items with visual warning styling.
6. THE Frontend SHALL show follow-up suggestions with recommended topics and participants.

### Requirement 6: Security and Permissions

**User Story:** As a developer, I want the agent to operate with least-privilege permissions, so that it can only access the data and services it needs.

#### Acceptance Criteria

1. THE Agent_Lambda IAM role SHALL have permissions to: read from the data S3 bucket, write to the agent_actions S3 key prefix, invoke Bedrock, and publish to the Notification_Topic.
2. THE Agent_Lambda IAM role SHALL include the MZJTeamBoundary permissions boundary.
3. THE Notification_Topic SHALL use server-side encryption.
4. THE Agent_Lambda SHALL NOT have permissions to modify meeting reports or transcripts.

### Requirement 7: Resource Naming and Tagging

**User Story:** As a developer, I want all new resources to follow the established naming and tagging conventions.

#### Acceptance Criteria

1. THE Agent_Lambda SHALL be named `Pranav-meeting-minutes-agent`.
2. THE Notification_Topic SHALL be named `Pranav-meeting-minutes-notifications`.
3. THE Agent_Lambda IAM role SHALL be named `Pranav-meeting-minutes-agent-role`.
4. ALL new resources SHALL be tagged with `User=Pranav` and `Project=meeting-minutes`.
5. ALL resources SHALL be deployed in `ap-northeast-1`.

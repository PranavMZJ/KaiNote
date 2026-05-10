/**
 * Typed API client for the Meeting Minutes REST API.
 *
 * Communicates with the API Gateway REST endpoints using JWT authorization.
 * Base URL is configured via the NEXT_PUBLIC_API_GATEWAY_URL environment variable.
 *
 * Requirements: 1.5, 9.1, 13.2, 13.3
 */

// ---------------------------------------------------------------------------
// Response types (matching backend API handler shapes)
// ---------------------------------------------------------------------------

export type MeetingStatus = "pending" | "processing" | "completed" | "failed";

export interface Meeting {
  meetingId: string;
  userId: string;
  status: MeetingStatus;
  createdAt: string;
  updatedAt: string;
  meeting_title?: string;
  stepFunctionExecutionArn?: string | null;
  currentStep?: string | null;
  error?: string | null;
  transcriptKey?: string | null;
  reportKey?: string | null;
}

export interface Decision {
  decision: string;
  rationale: string;
  owner: string | null;
  evidence: string;
  timestamp: string | null;
}

export interface ActionItem {
  task: string;
  owner: string | null;
  due_date: string | null;
  priority: "low" | "medium" | "high";
  evidence: string;
  timestamp: string | null;
  confidence: number;
  needs_human_review: boolean;
}

export interface MinutesReport {
  schema_version: string;
  meeting_title: string;
  meeting_datetime: string;
  participants: string[];
  summary: string;
  agenda_items: string[];
  key_discussion_points: string[];
  decisions: Decision[];
  action_items: ActionItem[];
  risks_blockers: string[];
  open_questions: string[];
  follow_up_needed: boolean;
}

export interface ListMeetingsResponse {
  meetings: Meeting[];
}

export interface GetReportResponse {
  report: MinutesReport;
  version: "original" | "edited";
}

export interface SaveReportResponse {
  message: string;
  key: string;
}

export interface DownloadResponse {
  downloadUrl: string;
  key: string;
}

export interface RetryResponse {
  message: string;
  meetingId: string;
  executionArn: string;
}

export interface AgentNotification {
  recipient: string;
  task: string;
  due_date: string | null;
  priority: string;
  sent_at: string;
  message_id: string | null;
  error?: string;
}

export interface OverdueItem {
  original_task: string;
  original_owner: string;
  original_due_date: string | null;
  current_meeting_reference: string;
  status: "overdue" | "recurring";
}

export interface FollowUpSuggestion {
  recommended: boolean;
  reason: string;
  suggested_topics: string[];
  suggested_participants: string[];
  recommended_timeframe: string;
}

export interface AgentReport {
  agent_execution_timestamp: string;
  meeting_id: string;
  meeting_title: string;
  notifications_sent: AgentNotification[];
  overdue_items: OverdueItem[];
  follow_up_suggestion: FollowUpSuggestion | null;
}

export interface GetAgentReportResponse {
  agentReport: AgentReport | null;
}

export interface ApiError {
  error: string;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiClientError extends Error {
  constructor(
    message: string,
    public readonly statusCode: number,
    public readonly body?: ApiError,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

// ---------------------------------------------------------------------------
// Client factory
// ---------------------------------------------------------------------------

export interface ApiClientOptions {
  /** Function that returns a JWT access token, or null if unauthenticated. */
  getToken: () => Promise<string | null>;
  /** Override the base URL (defaults to NEXT_PUBLIC_API_GATEWAY_URL). */
  baseUrl?: string;
}

export interface ApiClient {
  /** GET /meetings — list the authenticated user's meetings. */
  listMeetings(): Promise<ListMeetingsResponse>;

  /** GET /meetings/{meetingId} — get meeting details and status. */
  getMeeting(meetingId: string): Promise<Meeting>;

  /** GET /meetings/{meetingId}/report — get the generated report. */
  getReport(meetingId: string): Promise<GetReportResponse>;

  /** PUT /meetings/{meetingId}/report — save an edited report. */
  saveReport(meetingId: string, report: MinutesReport): Promise<SaveReportResponse>;

  /** GET /meetings/{meetingId}/report/download — get a pre-signed download URL. */
  getReportDownloadUrl(meetingId: string): Promise<DownloadResponse>;

  /** POST /meetings/{meetingId}/retry — retry failed minutes generation. */
  retryMeeting(meetingId: string): Promise<RetryResponse>;

  /** GET /meetings/{meetingId}/agent-report — get the agent actions report. */
  getAgentReport(meetingId: string): Promise<GetAgentReportResponse>;
}

/**
 * Create a typed API client for the Meeting Minutes REST API.
 *
 * Usage:
 * ```ts
 * const api = createApiClient({ getToken: () => auth.getToken() });
 * const { meetings } = await api.listMeetings();
 * ```
 */
export function createApiClient(options: ApiClientOptions): ApiClient {
  const baseUrl =
    options.baseUrl ??
    (typeof process !== "undefined"
      ? process.env.NEXT_PUBLIC_API_GATEWAY_URL ?? ""
      : "");

  async function request<T>(
    path: string,
    init?: RequestInit,
  ): Promise<T> {
    const token = await options.getToken();

    const headers: Record<string, string> = {
      ...(init?.headers as Record<string, string> | undefined),
    };

    // JWT Authorization header
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    if (init?.body) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers,
    });

    // Parse body (may be empty for some error responses)
    let body: unknown;
    const text = await response.text();
    try {
      body = text ? JSON.parse(text) : undefined;
    } catch {
      body = undefined;
    }

    if (!response.ok) {
      throw new ApiClientError(
        (body as ApiError)?.error ?? `Request failed with status ${response.status}`,
        response.status,
        body as ApiError | undefined,
      );
    }

    return body as T;
  }

  return {
    listMeetings() {
      return request<ListMeetingsResponse>("/meetings");
    },

    getMeeting(meetingId: string) {
      return request<Meeting>(`/meetings/${encodeURIComponent(meetingId)}`);
    },

    getReport(meetingId: string) {
      return request<GetReportResponse>(
        `/meetings/${encodeURIComponent(meetingId)}/report`,
      );
    },

    saveReport(meetingId: string, report: MinutesReport) {
      return request<SaveReportResponse>(
        `/meetings/${encodeURIComponent(meetingId)}/report`,
        {
          method: "PUT",
          body: JSON.stringify(report),
        },
      );
    },

    getReportDownloadUrl(meetingId: string) {
      return request<DownloadResponse>(
        `/meetings/${encodeURIComponent(meetingId)}/report/download`,
      );
    },

    retryMeeting(meetingId: string) {
      return request<RetryResponse>(
        `/meetings/${encodeURIComponent(meetingId)}/retry`,
        { method: "POST" },
      );
    },

    getAgentReport(meetingId: string) {
      return request<GetAgentReportResponse>(
        `/meetings/${encodeURIComponent(meetingId)}/agent-report`,
      );
    },
  };
}

/**
 * Unit tests for the Meeting Minutes API client.
 *
 * Validates typed request/response handling, JWT authorization header
 * injection, and error handling.
 */

import {
  createApiClient,
  ApiClient,
  ApiClientError,
  type MinutesReport,
} from "../client";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const TEST_BASE_URL = "https://api.example.com";
const TEST_TOKEN = "test-jwt-token";

function mockGetToken(token: string | null = TEST_TOKEN) {
  return jest.fn().mockResolvedValue(token);
}

function mockFetchResponse(body: unknown, status = 200) {
  return jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

function buildClient(
  getToken = mockGetToken(),
  baseUrl = TEST_BASE_URL,
): ApiClient {
  return createApiClient({ getToken, baseUrl });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("createApiClient", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // ---- Authorization header ----

  it("includes JWT Authorization header when token is available", async () => {
    const fetchMock = mockFetchResponse({ meetings: [] });
    global.fetch = fetchMock;

    const client = buildClient();
    await client.listMeetings();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Authorization"]).toBe(`Bearer ${TEST_TOKEN}`);
  });

  it("omits Authorization header when token is null", async () => {
    const fetchMock = mockFetchResponse({ meetings: [] });
    global.fetch = fetchMock;

    const client = buildClient(mockGetToken(null));
    await client.listMeetings();

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers["Authorization"]).toBeUndefined();
  });

  // ---- listMeetings ----

  it("listMeetings sends GET /meetings", async () => {
    const meetings = [
      { meetingId: "m1", status: "completed", createdAt: "2024-01-01T00:00:00Z" },
    ];
    global.fetch = mockFetchResponse({ meetings });

    const client = buildClient();
    const result = await client.listMeetings();

    expect(result.meetings).toEqual(meetings);
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings`);
  });

  // ---- getMeeting ----

  it("getMeeting sends GET /meetings/{meetingId}", async () => {
    const meeting = { meetingId: "m1", status: "processing" };
    global.fetch = mockFetchResponse(meeting);

    const client = buildClient();
    const result = await client.getMeeting("m1");

    expect(result.meetingId).toBe("m1");
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings/m1`);
  });

  // ---- getReport ----

  it("getReport sends GET /meetings/{meetingId}/report", async () => {
    const report = { report: { meeting_title: "Test" }, version: "original" };
    global.fetch = mockFetchResponse(report);

    const client = buildClient();
    const result = await client.getReport("m1");

    expect(result.version).toBe("original");
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings/m1/report`);
  });

  // ---- saveReport ----

  it("saveReport sends PUT /meetings/{meetingId}/report with body", async () => {
    global.fetch = mockFetchResponse({ message: "Report saved", key: "k" });

    const client = buildClient();
    const report: MinutesReport = {
      schema_version: "v1",
      meeting_title: "Test",
      meeting_datetime: "2024-01-01T00:00:00Z",
      participants: [],
      summary: "Summary",
      agenda_items: [],
      key_discussion_points: [],
      decisions: [],
      action_items: [],
      risks_blockers: [],
      open_questions: [],
      follow_up_needed: false,
    };

    const result = await client.saveReport("m1", report);

    expect(result.message).toBe("Report saved");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings/m1/report`);
    expect(init.method).toBe("PUT");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual(report);
  });

  // ---- getReportDownloadUrl ----

  it("getReportDownloadUrl sends GET /meetings/{meetingId}/report/download", async () => {
    global.fetch = mockFetchResponse({
      downloadUrl: "https://s3.example.com/signed",
      key: "k",
    });

    const client = buildClient();
    const result = await client.getReportDownloadUrl("m1");

    expect(result.downloadUrl).toBe("https://s3.example.com/signed");
    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings/m1/report/download`);
  });

  // ---- retryMeeting ----

  it("retryMeeting sends POST /meetings/{meetingId}/retry", async () => {
    global.fetch = mockFetchResponse({
      message: "Retry started",
      meetingId: "m1",
      executionArn: "arn:aws:states:...",
    });

    const client = buildClient();
    const result = await client.retryMeeting("m1");

    expect(result.message).toBe("Retry started");
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings/m1/retry`);
    expect(init.method).toBe("POST");
  });

  // ---- Error handling ----

  it("throws ApiClientError on non-OK response", async () => {
    global.fetch = mockFetchResponse({ error: "Not found" }, 404);

    const client = buildClient();

    await expect(client.getMeeting("missing")).rejects.toThrow(ApiClientError);
    await expect(client.getMeeting("missing")).rejects.toMatchObject({
      statusCode: 404,
      message: "Not found",
    });
  });

  it("throws ApiClientError with generic message when body has no error field", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: () => Promise.resolve(""),
    });

    const client = buildClient();

    await expect(client.listMeetings()).rejects.toThrow(ApiClientError);
    await expect(client.listMeetings()).rejects.toMatchObject({
      statusCode: 500,
    });
  });

  // ---- URL encoding ----

  it("encodes meetingId in URL path", async () => {
    global.fetch = mockFetchResponse({ meetingId: "a/b" });

    const client = buildClient();
    await client.getMeeting("a/b");

    const [url] = (global.fetch as jest.Mock).mock.calls[0];
    expect(url).toBe(`${TEST_BASE_URL}/meetings/a%2Fb`);
  });
});

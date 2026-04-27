/**
 * Tests for the cognito module's lazy initialization and exported functions.
 * We mock amazon-cognito-identity-js to avoid real Cognito calls.
 */

// Store original env
const originalEnv = process.env;

beforeEach(() => {
  jest.resetModules();
  process.env = {
    ...originalEnv,
    NEXT_PUBLIC_COGNITO_USER_POOL_ID: "ap-northeast-1_TestPool",
    NEXT_PUBLIC_COGNITO_APP_CLIENT_ID: "test-client-id-123",
  };
});

afterEach(() => {
  process.env = originalEnv;
});

// Mock the entire amazon-cognito-identity-js module
jest.mock("amazon-cognito-identity-js", () => {
  const mockSession = {
    isValid: () => true,
    getAccessToken: () => ({ getJwtToken: () => "mock-access-token" }),
    getIdToken: () => ({
      getJwtToken: () => "mock-id-token",
      decodePayload: () => ({
        email: "test@example.com",
        name: "Test User",
        sub: "sub-123",
      }),
    }),
  };

  const mockUser = {
    authenticateUser: jest.fn((_details, callbacks) => {
      callbacks.onSuccess(mockSession);
    }),
    confirmRegistration: jest.fn((_code, _force, callback) => {
      callback(null, "SUCCESS");
    }),
    getSession: jest.fn((callback: (err: Error | null, session: unknown) => void) => {
      callback(null, mockSession);
    }),
    signOut: jest.fn(),
  };

  const MockCognitoUserPool = jest.fn().mockImplementation(() => ({
    signUp: jest.fn(
      (
        _username: string,
        _password: string,
        _attrs: unknown[],
        _validations: unknown[],
        callback: (err: Error | null, result?: { user: unknown }) => void
      ) => {
        callback(null, { user: mockUser });
      }
    ),
    getCurrentUser: jest.fn(() => mockUser),
  }));

  const MockCognitoUser = jest.fn().mockImplementation(() => mockUser);

  return {
    CognitoUserPool: MockCognitoUserPool,
    CognitoUser: MockCognitoUser,
    AuthenticationDetails: jest.fn(),
    CognitoUserAttribute: jest.fn().mockImplementation((data) => data),
  };
});

describe("cognito module", () => {
  it("signIn resolves with a session", async () => {
    const { signIn } = await import("../cognito");
    const session = await signIn("test@example.com", "Password1!");
    expect(session).toBeDefined();
    expect(session.getAccessToken().getJwtToken()).toBe("mock-access-token");
  });

  it("signUp resolves with a user", async () => {
    const { signUp } = await import("../cognito");
    const user = await signUp("test@example.com", "Password1!", "Test User");
    expect(user).toBeDefined();
  });

  it("confirmSignUp resolves with SUCCESS", async () => {
    const { confirmSignUp } = await import("../cognito");
    const result = await confirmSignUp("test@example.com", "123456");
    expect(result).toBe("SUCCESS");
  });

  it("signOut does not throw", async () => {
    const { signOut } = await import("../cognito");
    expect(() => signOut()).not.toThrow();
  });

  it("getSession returns a session", async () => {
    const { getSession } = await import("../cognito");
    const session = await getSession();
    expect(session).toBeDefined();
    expect(session?.isValid()).toBe(true);
  });

  it("getAccessToken returns the token string", async () => {
    const { getAccessToken } = await import("../cognito");
    const token = await getAccessToken();
    expect(token).toBe("mock-access-token");
  });

  it("getIdToken returns the token string", async () => {
    const { getIdToken } = await import("../cognito");
    const token = await getIdToken();
    expect(token).toBe("mock-id-token");
  });
});

describe("cognito module without env vars", () => {
  it("signOut does not throw when pool is not configured", async () => {
    process.env = { ...originalEnv };
    delete process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID;
    delete process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID;

    // Need to re-import to get fresh module state
    jest.resetModules();

    // Re-mock after reset
    jest.mock("amazon-cognito-identity-js", () => {
      const MockCognitoUserPool = jest.fn().mockImplementation(() => {
        throw new Error("Both UserPoolId and ClientId are required.");
      });
      return {
        CognitoUserPool: MockCognitoUserPool,
        CognitoUser: jest.fn(),
        AuthenticationDetails: jest.fn(),
        CognitoUserAttribute: jest.fn(),
      };
    });

    const { signOut } = await import("../cognito");
    expect(() => signOut()).not.toThrow();
  });

  it("getSession returns null when pool is not configured", async () => {
    process.env = { ...originalEnv };
    delete process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID;
    delete process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID;

    jest.resetModules();

    jest.mock("amazon-cognito-identity-js", () => {
      const MockCognitoUserPool = jest.fn().mockImplementation(() => {
        throw new Error("Both UserPoolId and ClientId are required.");
      });
      return {
        CognitoUserPool: MockCognitoUserPool,
        CognitoUser: jest.fn(),
        AuthenticationDetails: jest.fn(),
        CognitoUserAttribute: jest.fn(),
      };
    });

    const { getSession } = await import("../cognito");
    const session = await getSession();
    expect(session).toBeNull();
  });
});

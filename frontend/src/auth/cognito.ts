import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
  CognitoUserSession,
} from "amazon-cognito-identity-js";

const userPoolId = process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? "";
const clientId = process.env.NEXT_PUBLIC_COGNITO_APP_CLIENT_ID ?? "";

let _userPool: CognitoUserPool | null = null;

/**
 * Lazily initialise the Cognito User Pool so that the module can be
 * imported during Next.js static export (where env vars may be empty)
 * without throwing.
 */
function getUserPool(): CognitoUserPool {
  if (!_userPool) {
    if (!userPoolId || !clientId) {
      throw new Error(
        "Cognito configuration missing: set NEXT_PUBLIC_COGNITO_USER_POOL_ID and NEXT_PUBLIC_COGNITO_APP_CLIENT_ID"
      );
    }
    _userPool = new CognitoUserPool({
      UserPoolId: userPoolId,
      ClientId: clientId,
    });
  }
  return _userPool;
}

/**
 * Sign in with email and password.
 * Returns the Cognito session containing JWT tokens.
 */
export function signIn(
  email: string,
  password: string
): Promise<CognitoUserSession> {
  const pool = getUserPool();
  const user = new CognitoUser({ Username: email, Pool: pool });
  const authDetails = new AuthenticationDetails({
    Username: email,
    Password: password,
  });

  return new Promise((resolve, reject) => {
    user.authenticateUser(authDetails, {
      onSuccess: (session) => resolve(session),
      onFailure: (err) => reject(err),
    });
  });
}

/**
 * Register a new user with email, password, and name.
 * Triggers email verification.
 */
export function signUp(
  email: string,
  password: string,
  name: string
): Promise<CognitoUser | undefined> {
  const pool = getUserPool();
  const attributes = [
    new CognitoUserAttribute({ Name: "email", Value: email }),
    new CognitoUserAttribute({ Name: "name", Value: name }),
  ];

  return new Promise((resolve, reject) => {
    pool.signUp(email, password, attributes, [], (err, result) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(result?.user);
    });
  });
}

/**
 * Confirm registration with the verification code sent to the user's email.
 */
export function confirmSignUp(
  email: string,
  code: string
): Promise<string> {
  const pool = getUserPool();
  const user = new CognitoUser({ Username: email, Pool: pool });

  return new Promise((resolve, reject) => {
    user.confirmRegistration(code, true, (err, result) => {
      if (err) {
        reject(err);
        return;
      }
      resolve(result as string);
    });
  });
}

/**
 * Sign out the current user and clear the session.
 */
export function signOut(): void {
  try {
    const pool = getUserPool();
    const user = pool.getCurrentUser();
    if (user) {
      user.signOut();
    }
  } catch {
    // Pool not configured — nothing to sign out of
  }
}

/**
 * Get the current authenticated session.
 * Returns null if no user is signed in or the session is invalid.
 */
export function getSession(): Promise<CognitoUserSession | null> {
  let pool: CognitoUserPool;
  try {
    pool = getUserPool();
  } catch {
    return Promise.resolve(null);
  }

  const user = pool.getCurrentUser();
  if (!user) {
    return Promise.resolve(null);
  }

  return new Promise((resolve, reject) => {
    user.getSession(
      (err: Error | null, session: CognitoUserSession | null) => {
        if (err) {
          reject(err);
          return;
        }
        resolve(session);
      }
    );
  });
}

/**
 * Get the access token string for API calls.
 * Returns null if no valid session exists.
 */
export async function getAccessToken(): Promise<string | null> {
  const session = await getSession();
  if (!session || !session.isValid()) {
    return null;
  }
  return session.getAccessToken().getJwtToken();
}

/**
 * Get the ID token string (contains user claims).
 * Returns null if no valid session exists.
 */
export async function getIdToken(): Promise<string | null> {
  const session = await getSession();
  if (!session || !session.isValid()) {
    return null;
  }
  return session.getIdToken().getJwtToken();
}

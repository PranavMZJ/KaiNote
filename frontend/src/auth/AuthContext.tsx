"use client";

import React, {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { CognitoUserSession } from "amazon-cognito-identity-js";
import * as cognito from "./cognito";

export interface AuthUser {
  email: string;
  name?: string;
  sub: string;
}

export interface AuthContextValue {
  /** The currently authenticated user, or null. */
  user: AuthUser | null;
  /** Whether the user is authenticated. */
  isAuthenticated: boolean;
  /** Whether the initial session check is still in progress. */
  isLoading: boolean;
  /** Sign in with email and password. */
  signIn: (email: string, password: string) => Promise<void>;
  /** Register a new account. */
  signUp: (email: string, password: string, name: string) => Promise<void>;
  /** Confirm registration with verification code. */
  confirmSignUp: (email: string, code: string) => Promise<void>;
  /** Sign out and clear session. */
  signOut: () => void;
  /** Get the current access token for API calls. */
  getToken: () => Promise<string | null>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(
  undefined
);

function extractUser(session: CognitoUserSession): AuthUser {
  const idToken = session.getIdToken();
  const payload = idToken.decodePayload();
  return {
    email: payload["email"] as string,
    name: payload["name"] as string | undefined,
    sub: payload["sub"] as string,
  };
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  // Store tokens in memory only — never persisted to localStorage
  const [session, setSession] = useState<CognitoUserSession | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    let cancelled = false;
    cognito
      .getSession()
      .then((existingSession) => {
        if (cancelled) return;
        if (existingSession && existingSession.isValid()) {
          setSession(existingSession);
          setUser(extractUser(existingSession));
        }
      })
      .catch(() => {
        // No valid session — that's fine
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSignIn = useCallback(
    async (email: string, password: string) => {
      const newSession = await cognito.signIn(email, password);
      setSession(newSession);
      setUser(extractUser(newSession));
    },
    []
  );

  const handleSignUp = useCallback(
    async (email: string, password: string, name: string) => {
      await cognito.signUp(email, password, name);
    },
    []
  );

  const handleConfirmSignUp = useCallback(
    async (email: string, code: string) => {
      await cognito.confirmSignUp(email, code);
    },
    []
  );

  const handleSignOut = useCallback(() => {
    cognito.signOut();
    setSession(null);
    setUser(null);
  }, []);

  const getToken = useCallback(async (): Promise<string | null> => {
    if (!session || !session.isValid()) {
      // Try refreshing
      const refreshed = await cognito.getSession();
      if (refreshed && refreshed.isValid()) {
        setSession(refreshed);
        setUser(extractUser(refreshed));
        return refreshed.getAccessToken().getJwtToken();
      }
      return null;
    }
    return session.getAccessToken().getJwtToken();
  }, [session]);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated: !!user,
      isLoading,
      signIn: handleSignIn,
      signUp: handleSignUp,
      confirmSignUp: handleConfirmSignUp,
      signOut: handleSignOut,
      getToken,
    }),
    [
      user,
      isLoading,
      handleSignIn,
      handleSignUp,
      handleConfirmSignUp,
      handleSignOut,
      getToken,
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

import React from "react";
import { renderHook } from "@testing-library/react";
import { useAuth } from "../useAuth";
import { AuthContext } from "../AuthContext";
import type { AuthContextValue } from "../AuthContext";

function createMockAuthValue(
  overrides: Partial<AuthContextValue> = {}
): AuthContextValue {
  return {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    signIn: jest.fn(),
    signUp: jest.fn(),
    confirmSignUp: jest.fn(),
    signOut: jest.fn(),
    getToken: jest.fn().mockResolvedValue(null),
    ...overrides,
  };
}

describe("useAuth", () => {
  it("throws when used outside AuthProvider", () => {
    // Suppress console.error for the expected error
    const spy = jest.spyOn(console, "error").mockImplementation(() => {});
    expect(() => renderHook(() => useAuth())).toThrow(
      "useAuth must be used within an AuthProvider"
    );
    spy.mockRestore();
  });

  it("returns context value when used inside AuthProvider", () => {
    const mockValue = createMockAuthValue({
      user: { email: "test@example.com", sub: "sub-123", name: "Test" },
      isAuthenticated: true,
    });

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AuthContext.Provider value={mockValue}>{children}</AuthContext.Provider>
    );

    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user?.email).toBe("test@example.com");
    expect(result.current.user?.sub).toBe("sub-123");
  });

  it("exposes all expected methods", () => {
    const mockValue = createMockAuthValue();

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <AuthContext.Provider value={mockValue}>{children}</AuthContext.Provider>
    );

    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(typeof result.current.signIn).toBe("function");
    expect(typeof result.current.signUp).toBe("function");
    expect(typeof result.current.confirmSignUp).toBe("function");
    expect(typeof result.current.signOut).toBe("function");
    expect(typeof result.current.getToken).toBe("function");
  });
});

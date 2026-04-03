import { createContext, type PropsWithChildren, useContext, useEffect, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  clearSession,
  isSessionExpired,
  readStoredSession,
  subscribeAuthSession,
  type AuthSession,
} from "@/lib/api-client";
import type { AuthenticatedUser } from "@/types/api";

type AuthSessionContextValue = {
  session: AuthSession | null;
  user: AuthenticatedUser | null;
  isAuthenticated: boolean;
  logout: () => void;
};

const AuthSessionContext = createContext<AuthSessionContextValue | null>(null);

export function AuthSessionProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const storedSession = useSyncExternalStore(subscribeAuthSession, readStoredSession, () => null);
  const session = storedSession && !isSessionExpired(storedSession) ? storedSession : null;

  useEffect(() => {
    if (storedSession && session === null) {
      clearSession();
    }
  }, [session, storedSession]);

  useEffect(() => {
    if (session === null) {
      queryClient.clear();
    }
  }, [queryClient, session]);

  return (
    <AuthSessionContext.Provider
      value={{
        session,
        user: session?.user ?? null,
        isAuthenticated: session !== null,
        logout: () => {
          clearSession();
          queryClient.clear();
        },
      }}
    >
      {children}
    </AuthSessionContext.Provider>
  );
}

export function useAuthSession() {
  const context = useContext(AuthSessionContext);
  if (!context) {
    throw new Error("useAuthSession must be used within AuthSessionProvider.");
  }
  return context;
}

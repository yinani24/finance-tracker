"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { createClient } from "@/lib/supabase/client";
import type { Session, User } from "@supabase/supabase-js";

const MAX_SESSION_AGE_MS = 60 * 60 * 1000; // 1 hour

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  loading: boolean;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  session: null,
  loading: true,
  signOut: async () => {},
});

function isSessionExpired(session: Session): boolean {
  // Check if the access token's exp has passed
  if (session.expires_at && session.expires_at * 1000 < Date.now()) {
    return true;
  }
  // Enforce 1-hour max age: expires_at - expires_in = issued_at
  const expiresIn = session.expires_in ?? 3600;
  const expiresAt = session.expires_at ?? 0;
  const tokenIssuedAt = expiresAt - expiresIn;
  if (tokenIssuedAt > 0 && Date.now() - tokenIssuedAt * 1000 > MAX_SESSION_AGE_MS) {
    return true;
  }
  return false;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const hadSession = useRef(false);
  const supabase = createClient();

  const handleSignOut = useCallback(async () => {
    await supabase.auth.signOut();
    window.location.href = "/dashboard";
  }, [supabase]);

  const validateAndSetSession = useCallback(
    (newSession: Session | null) => {
      if (newSession && isSessionExpired(newSession)) {
        handleSignOut();
        return;
      }
      setSession(newSession);
      if (newSession) hadSession.current = true;
    },
    [handleSignOut]
  );

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      validateAndSetSession(session);
      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, session) => {
      validateAndSetSession(session);

      if (event === "SIGNED_OUT" && hadSession.current) {
        window.location.href = "/dashboard";
      }
    });

    // Check session expiry every minute
    const interval = setInterval(() => {
      supabase.auth.getSession().then(({ data: { session } }) => {
        if (session && isSessionExpired(session)) {
          handleSignOut();
        }
      });
    }, 60_000);

    return () => {
      subscription.unsubscribe();
      clearInterval(interval);
    };
  }, [supabase, validateAndSetSession, handleSignOut]);

  return (
    <AuthContext.Provider
      value={{
        user: session?.user ?? null,
        session,
        loading,
        signOut: handleSignOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

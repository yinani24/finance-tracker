"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  EMPTY_SESSION,
  type HeldCard,
  type ImportRecord,
  type CreditStanding,
  type SessionState,
  type SessionStep,
  type SessionTransaction,
} from "./types";

/**
 * The client-only session.
 *
 * Backed by `sessionStorage`, deliberately: it survives an accidental refresh
 * but the browser clears it when the tab closes, which is exactly the lifetime
 * the product wants. Nothing here is ever sent to the API or persisted in a
 * database — the user's statements and card details stay on their machine.
 *
 * `localStorage` would outlive the tab and `useState` alone would lose
 * everything on reload, so neither fits.
 */

const STORAGE_KEY = "ft.session.v1";

interface SessionContextValue {
  session: SessionState;
  ready: boolean;
  setStep: (step: SessionStep) => void;
  setCredit: (credit: CreditStanding) => void;
  addCard: (card: Omit<HeldCard, "id">) => void;
  updateCard: (id: string, patch: Partial<HeldCard>) => void;
  removeCard: (id: string) => void;
  addTransactions: (
    rows: Omit<SessionTransaction, "id">[],
    record: Omit<ImportRecord, "id" | "importedAt">
  ) => void;
  clear: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

function newId() {
  return globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2);
}

function readStored(): SessionState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SessionState;
    // Defensive: a shape change between versions must not crash the app.
    return { ...EMPTY_SESSION, ...parsed };
  } catch {
    return null;
  }
}

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionState>(EMPTY_SESSION);
  // Hydration guard: sessionStorage is unavailable during SSR, so the first
  // client render must match the server's (empty) output before we restore.
  const [ready, setReady] = useState(false);
  const hydrated = useRef(false);

  useEffect(() => {
    const stored = readStored();
    if (stored) setSession(stored);
    hydrated.current = true;
    setReady(true);
  }, []);

  useEffect(() => {
    if (!hydrated.current) return;
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } catch {
      // Quota or a privacy mode that blocks storage: the session still works
      // in memory for this page, it just won't survive a refresh.
    }
  }, [session]);

  const setStep = useCallback((step: SessionStep) => {
    setSession((s) => ({ ...s, step }));
  }, []);

  const setCredit = useCallback((credit: CreditStanding) => {
    setSession((s) => ({ ...s, credit: { ...s.credit, ...credit } }));
  }, []);

  const addCard = useCallback((card: Omit<HeldCard, "id">) => {
    setSession((s) => ({ ...s, heldCards: [...s.heldCards, { ...card, id: newId() }] }));
  }, []);

  const updateCard = useCallback((id: string, patch: Partial<HeldCard>) => {
    setSession((s) => ({
      ...s,
      heldCards: s.heldCards.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    }));
  }, []);

  const removeCard = useCallback((id: string) => {
    setSession((s) => ({ ...s, heldCards: s.heldCards.filter((c) => c.id !== id) }));
  }, []);

  const addTransactions = useCallback(
    (
      rows: Omit<SessionTransaction, "id">[],
      record: Omit<ImportRecord, "id" | "importedAt">
    ) => {
      setSession((s) => {
        // Dedupe on (date, merchant, amount) so re-importing an overlapping
        // statement doesn't double-count — the same guarantee the server path
        // gave via its dedupe hash.
        const seen = new Set(
          s.transactions.map((t) => `${t.occurredOn}|${t.merchant}|${t.amount}`)
        );
        const fresh = rows
          .filter((r) => !seen.has(`${r.occurredOn}|${r.merchant}|${r.amount}`))
          .map((r) => ({ ...r, id: newId() }));
        return {
          ...s,
          transactions: [...s.transactions, ...fresh],
          imports: [
            { ...record, added: fresh.length, id: newId(), importedAt: new Date().toISOString() },
            ...s.imports,
          ],
        };
      });
    },
    []
  );

  const clear = useCallback(() => {
    setSession(EMPTY_SESSION);
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      /* nothing to clean up if storage is unavailable */
    }
  }, []);

  const value = useMemo(
    () => ({
      session,
      ready,
      setStep,
      setCredit,
      addCard,
      updateCard,
      removeCard,
      addTransactions,
      clear,
    }),
    [session, ready, setStep, setCredit, addCard, updateCard, removeCard, addTransactions, clear]
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside <SessionProvider>");
  return ctx;
}

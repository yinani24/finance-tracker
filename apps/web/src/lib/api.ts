import type {
  Account,
  Card,
  CardBonus,
  CardBonusSearchResult,
  Goal,
  ImportRecord,
  ImportSummary,
  Insight,
  InsightSummary,
  LinkTokenResponse,
  NextCardResponse,
  PlaidItem,
  PortfolioResponse,
  SpendingProfile,
  SyncResult,
  Transaction,
  User,
  UserPreference,
} from "./types";

import { createClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Is a reachable API configured?
 *
 * Statement parsing, the spending profile, subscriptions and income all run in
 * the browser, so the app is useful with no backend at all. Only card ranking
 * needs one, because it reads the public card dataset. On a deployment with no
 * API configured the default would be `localhost:8000`, which exists on the
 * developer's machine and nowhere else — so every visitor would sit in front of
 * a spinner that never resolves. Callers gate those queries on this instead.
 */
export const hasApi =
  Boolean(process.env.NEXT_PUBLIC_API_URL) ||
  (typeof window !== "undefined" && window.location.hostname === "localhost");

// Global callback for session expiry — set by AuthProvider
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

async function getAccessToken(
  forceRefresh = false
): Promise<string | null> {
  const supabase = createClient();
  if (!supabase) return null;
  if (forceRefresh) {
    const { data, error } = await supabase.auth.refreshSession();
    if (error || !data.session) return null;
    return data.session.access_token;
  }
  const {
    data: { session },
  } = await supabase.auth.getSession();
  return session?.access_token ?? null;
}

async function fetchWithAuth(
  path: string,
  token: string | null,
  options?: RequestInit
): Promise<Response> {
  // FormData (file uploads) must NOT carry an explicit Content-Type — the
  // browser sets `multipart/form-data` with the correct boundary itself. Only
  // default to JSON for non-FormData bodies.
  const isFormData =
    typeof FormData !== "undefined" && options?.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...options?.headers as Record<string, string>,
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  let res = await fetchWithAuth(path, token, options);

  if (res.status === 401) {
    // Token might be stale — try refreshing once
    const freshToken = await getAccessToken(true);
    if (freshToken) {
      res = await fetchWithAuth(path, freshToken, options);
    }
    if (res.status === 401) {
      onSessionExpired?.();
      throw new Error("Session expired");
    }
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// User
export const getMe = () => request<User>("/me");
export const updateMe = (data: { full_name?: string }) =>
  request<User>("/me", { method: "PATCH", body: JSON.stringify(data) });
export const getPreferences = () => request<UserPreference>("/me/preferences");
export const updatePreferences = (data: Partial<UserPreference>) =>
  request<UserPreference>("/me/preferences", {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// Accounts
export const getAccounts = () => request<Account[]>("/accounts");
export const createAccount = (data: Partial<Account>) =>
  request<Account>("/accounts", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const updateAccount = (id: number, data: Partial<Account>) =>
  request<Account>(`/accounts/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// Transactions
export const getTransactions = (params?: {
  category?: string;
  account_id?: number;
}) => {
  const search = new URLSearchParams();
  if (params?.category) search.set("category", params.category);
  if (params?.account_id)
    search.set("account_id", String(params.account_id));
  const qs = search.toString();
  return request<Transaction[]>(`/transactions${qs ? `?${qs}` : ""}`);
};
export const createTransaction = (data: Partial<Transaction>) =>
  request<Transaction>("/transactions", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const updateTransaction = (id: number, data: Partial<Transaction>) =>
  request<Transaction>(`/transactions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// Goals
export const getGoals = () => request<Goal[]>("/goals");
export const createGoal = (data: Partial<Goal>) =>
  request<Goal>("/goals", { method: "POST", body: JSON.stringify(data) });
export const updateGoal = (id: number, data: Partial<Goal>) =>
  request<Goal>(`/goals/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });

// Cards
export const getCards = () => request<Card[]>("/cards");
export const createCard = (data: Partial<Card>) =>
  request<Card>("/cards", { method: "POST", body: JSON.stringify(data) });
export const updateCard = (id: number, data: Partial<Card>) =>
  request<Card>(`/cards/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
export const deleteCard = (id: number) =>
  request<void>(`/cards/${id}`, { method: "DELETE" });

// Card Bonuses (public — no auth needed)
export const searchCardBonuses = (params?: {
  q?: string;
  issuer?: string;
  network?: string;
  is_business?: boolean;
  max_annual_fee?: number;
  limit?: number;
  offset?: number;
}) => {
  const search = new URLSearchParams();
  if (params?.q) search.set("q", params.q);
  if (params?.issuer) search.set("issuer", params.issuer);
  if (params?.network) search.set("network", params.network);
  if (params?.is_business !== undefined)
    search.set("is_business", String(params.is_business));
  if (params?.max_annual_fee !== undefined)
    search.set("max_annual_fee", String(params.max_annual_fee));
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return request<CardBonusSearchResult>(
    `/card-bonuses${qs ? `?${qs}` : ""}`
  );
};
export const getCardBonusIssuers = () =>
  request<string[]>("/card-bonuses/issuers");
// Single card by its `cardId` (public — no auth). The endpoint returns 404 for
// an unknown id, which surfaces here as a thrown `API 404: ...` error.
export const getCardBonus = (cardId: string) =>
  request<CardBonus>(`/card-bonuses/${encodeURIComponent(cardId)}`);

// Plaid
export const getPlaidItems = () => request<PlaidItem[]>("/plaid/items");
export const createLinkToken = () =>
  request<LinkTokenResponse>("/plaid/link-token", { method: "POST" });
export const exchangePublicToken = (data: {
  public_token: string;
  institution_id?: string;
  institution_name?: string;
}) =>
  request<PlaidItem>("/plaid/exchange-token", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const syncPlaidItem = (itemId: number) =>
  request<SyncResult>(`/plaid/items/${itemId}/sync`, { method: "POST" });
export const deletePlaidItem = (itemId: number) =>
  request<void>(`/plaid/items/${itemId}`, { method: "DELETE" });

// Recommendations
export const getNextCardRecommendations = () =>
  request<NextCardResponse>("/recommendations/next-card");

/**
 * Rank cards from a profile the browser derived locally.
 *
 * The GET variant ranks against transactions stored server-side, which the
 * client-only flow never writes — so it would answer from stale data. This
 * sends aggregates instead: monthly spend and a category breakdown, which is
 * all the ranking engine reads. No merchant names, dates, amounts or account
 * numbers are transmitted, and the server stores nothing.
 */
export interface StatelessProfileRequest {
  avg_monthly_spend: number;
  category_breakdown: Record<string, number>;
  held_cards: { name: string; issuer?: string; annual_fee?: number }[];
  credit_score_band?: string | null;
  recent_card_applications?: number | null;
  max_results?: number;
}

export const postStatelessRecommendations = (body: StatelessProfileRequest) =>
  request<NextCardResponse>("/recommendations/next-card/stateless", {
    method: "POST",
    body: JSON.stringify(body),
  });

export interface StatelessPortfolioResponse {
  analyses: {
    name: string;
    issuer?: string;
    estimated_annual_value?: number;
    annual_fee?: number;
    net_value?: number;
    verdict?: string;
  }[];
  best_per_category: {
    category: string;
    best_card: { name: string; issuer: string } | null;
    rate: number | null;
    rationale?: string;
    card_rates?: Record<string, number>;
  }[];
  /** The best card on the market per category, as cash-equivalent percent. */
  best_available_per_category: {
    category: string;
    card: {
      cardId: string;
      name: string;
      issuer: string;
      annualFee: number;
      url?: string | null;
    };
    rate: number;
    raw_rate: number;
    currency?: string | null;
  }[];
}

export const postStatelessPortfolio = (body: StatelessProfileRequest) =>
  request<StatelessPortfolioResponse>("/recommendations/portfolio/stateless", {
    method: "POST",
    body: JSON.stringify(body),
  });
export const getPortfolioAnalysis = () =>
  request<PortfolioResponse>("/recommendations/portfolio");
export const getSpendingProfile = () =>
  request<SpendingProfile>("/recommendations/spending-profile");
export const refreshRecommendations = () =>
  request<{ status: string }>("/recommendations/refresh", { method: "POST" });

// Insights
export const getInsights = (params?: { engine?: string; effort?: string; limit?: number; offset?: number }) => {
  const search = new URLSearchParams();
  if (params?.engine) search.set("engine", params.engine);
  if (params?.effort) search.set("effort", params.effort);
  if (params?.limit) search.set("limit", String(params.limit));
  if (params?.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return request<Insight[]>(`/insights${qs ? `?${qs}` : ""}`);
};
export const getInsightsSummary = () => request<InsightSummary>("/insights/summary");
export const getInsight = (id: number) => request<Insight>(`/insights/${id}`);
export const dismissInsight = (id: number, reason?: string) =>
  request<Insight>(`/insights/${id}/dismiss`, { method: "POST", body: JSON.stringify({ reason }) });
export const snoozeInsight = (id: number, until: string) =>
  request<Insight>(`/insights/${id}/snooze`, { method: "POST", body: JSON.stringify({ until }) });
export const markInsightActedOn = (id: number) =>
  request<Insight>(`/insights/${id}/acted-on`, { method: "POST" });
export const markInsightsSeen = () =>
  request<{ marked: number }>("/insights/mark-seen", { method: "POST" });
export const getInsightsHistory = () => request<Insight[]>("/insights/history");
export const refreshInsights = () =>
  request<{ status: string }>("/insights/refresh", { method: "POST" });

// Statement imports (CSV). Uploads a bank/card statement file for an account;
// the backend parses, dedupes, and creates transactions, returning a per-run
// summary. `getImports` lists past import runs and their status.
export const createImport = (accountId: number, file: File) => {
  const form = new FormData();
  form.append("file", file);
  form.append("account_id", String(accountId));
  return request<ImportSummary>("/imports", { method: "POST", body: form });
};
export const getImports = () => request<ImportRecord[]>("/imports");

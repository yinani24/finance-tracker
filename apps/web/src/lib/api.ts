import type {
  Account,
  Card,
  CardBonusSearchResult,
  Goal,
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

// Global callback for session expiry — set by AuthProvider
let onSessionExpired: (() => void) | null = null;

export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

async function getAccessToken(
  forceRefresh = false
): Promise<string | null> {
  const supabase = createClient();
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

async function fetchWithAuth<T>(
  path: string,
  token: string | null,
  options?: RequestInit
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...options?.headers as Record<string, string>,
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, { ...options, headers });
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = await getAccessToken();
  let res = await fetchWithAuth<T>(path, token, options);

  if (res.status === 401) {
    // Token might be stale — try refreshing once
    const freshToken = await getAccessToken(true);
    if (freshToken) {
      res = await fetchWithAuth<T>(path, freshToken, options);
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

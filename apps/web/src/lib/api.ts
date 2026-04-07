import type {
  Account,
  Card,
  Goal,
  LinkTokenResponse,
  PlaidItem,
  SyncResult,
  Transaction,
  User,
  UserPreference,
} from "./types";

import { createClient } from "@/lib/supabase/client";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (session?.access_token) {
    return { Authorization: `Bearer ${session.access_token}` };
  }
  return {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const authHeaders = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders,
      ...options?.headers,
    },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// User
export const getMe = () => request<User>("/me");
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

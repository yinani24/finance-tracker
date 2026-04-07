export interface User {
  id: number;
  email: string;
  auth_provider: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserPreference {
  user_id: number;
  theme: string;
  timezone: string;
  created_at: string;
  updated_at: string;
}

export interface Account {
  id: number;
  user_id: number;
  name: string;
  type: string;
  institution_name: string | null;
  external_account_id: string | null;
  balance: number;
  currency: string;
  last_synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Transaction {
  id: number;
  user_id: number;
  account_id: number;
  external_id: string | null;
  occurred_on: string;
  posted_at: string | null;
  amount: number;
  merchant: string;
  normalized_merchant: string | null;
  category: string | null;
  is_income: boolean;
  is_savings: boolean;
  source: string | null;
  source_import_id: number | null;
  dedupe_hash: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface Goal {
  id: number;
  user_id: number;
  name: string;
  goal_type: string;
  target_amount: number;
  current_amount: number;
  deadline: string | null;
  is_monthly: boolean;
  created_at: string;
  updated_at: string;
}

export interface Card {
  id: number;
  user_id: number;
  name: string;
  network: string | null;
  annual_fee: number;
  rewards_config_json: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlaidItem {
  id: number;
  user_id: number;
  item_id: string;
  institution_id: string | null;
  institution_name: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SyncResult {
  accounts_synced: number;
  transactions_added: number;
  transactions_modified: number;
  transactions_removed: number;
}

export interface LinkTokenResponse {
  link_token: string;
  expiration: string;
}

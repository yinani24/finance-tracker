export interface User {
  id: number;
  email: string;
  full_name: string | null;
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

export interface CardBonusOffer {
  spend: number;
  amount: { amount: number; currency?: string }[];
  days: number;
  credits: { description: string; value: number; weight: number; currency: string }[];
  expiration?: string;
  url?: string;
}

export interface CardBonus {
  cardId: string;
  name: string;
  issuer: string;
  network: string;
  currency: string;
  isBusiness: boolean;
  annualFee: number;
  isAnnualFeeWaived: boolean;
  universalCashbackPercent: number;
  url: string;
  imageUrl: string;
  credits: { description: string; value: number; weight: number; currency: string }[];
  offers: CardBonusOffer[];
  discontinued: boolean;
}

export interface CardBonusSearchResult {
  total: number;
  limit: number;
  offset: number;
  // The `/card-bonuses` endpoint returns the page window under `results`
  // (see apps/api/app/services/card_bonuses.py:search_cards and the
  // `body["results"]` assertions in tests/test_card_bonuses.py).
  results: CardBonus[];
}

// Recommendations
export interface CategorySpend {
  category: string;
  monthly_avg: number;
  count: number;
  monthly_avg_count: number;
  avg_per_txn: number;
}

export interface TopMerchant {
  merchant: string;
  monthly_avg: number;
}

export interface SpendingProfile {
  user_id: number;
  period_start: string;
  period_end: string;
  avg_monthly_spend: number;
  categories: CategorySpend[];
  dining: CategorySpend | null;
  top_merchants: TopMerchant[];
  computed_at: string;
}

export interface NextCardRecommendation {
  card: CardBonus;
  score: number;
  bonus_value: number;
  months_to_hit: number;
  achievable: boolean;
  explanation: string;
}

export interface NextCardResponse {
  recommendations: NextCardRecommendation[];
  spending_profile: SpendingProfile;
}

export interface AlternativeCard {
  card: CardBonus;
  net_value: number;
  explanation: string;
}

export interface CardAnalysis {
  user_card: Record<string, unknown>;
  matched_card: CardBonus | null;
  estimated_annual_value: number;
  net_value: number;
  status: "good" | "underperforming" | "costing_money";
  explanation: string;
  alternatives: AlternativeCard[];
}

export interface PortfolioResponse {
  cards: CardAnalysis[];
  spending_profile: SpendingProfile;
}

export interface Insight {
  id: number;
  engine: string;
  kind: string;
  title: string;
  body: string;
  impact_one_time_cents: number;
  impact_annual_cents: number;
  effort: string;
  evidence_json: string;
  action_json: string | null;
  related_goal_id: number | null;
  status: string;
  snoozed_until: string | null;
  seen_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InsightSummary {
  total_active: number;
  total_annual_impact_cents: number;
  unread_count: number;
  by_engine: Record<string, number>;
}

// Result of one statement-import run (POST /imports response). `duplicates` and
// `skipped` are per-run counts so the UI can show exactly what a single upload did.
// A single data row that failed to parse during import (row = 1-based file
// line number, header is line 1).
export interface ImportRowError {
  row: number;
  reason: string;
}

export interface ImportSummary {
  import_id: number;
  account_id: number;
  provider: string;
  import_type: string;
  status: string;
  total_rows: number;
  added: number;
  duplicates: number;
  skipped: number;
  errors: ImportRowError[];
  error_message: string | null;
}

// Persisted status of an import (GET /imports and GET /imports/{id}).
export interface ImportRecord {
  id: number;
  account_id: number;
  provider: string;
  import_type: string;
  status: string;
  error_message: string | null;
  transaction_count: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

/**
 * Everything the app displays, derived from the session.
 *
 * The pages used to read the API, which is why an uploaded statement appeared
 * to vanish: it went into session memory and no page looked there. These
 * selectors close that gap — they are the read side of the client-only store,
 * computed from the same transactions the dropzone wrote.
 *
 * Pure functions over `SessionState`, so they are trivially testable and carry
 * no React or fetch dependency.
 */

import type { HeldCard, SessionState, SessionTransaction } from "./types";

/**
 * Money moving between the user's own accounts, which is neither earning nor
 * spending.
 *
 * Paying a credit card appears twice once both files are loaded: as a credit
 * on the card statement, and as a debit on the bank export. Counted naively
 * that inflates income by the payment and double-counts the spending — once as
 * the original charges, again as the payment covering them. Neither side is a
 * real flow, so both are excluded.
 */
const TRANSFER_PATTERNS = [
  /payment\s+thank\s*you/i,
  /automatic\s+payment/i,
  /\bautopay\b/i,
  /\bepay\b/i,
  /credit\s+crd/i,
  /card\s+payment/i,
  /online\s+transfer/i,
  /\btransfer\s+(to|from)\b/i,
];

export function isTransfer(merchant: string): boolean {
  return TRANSFER_PATTERNS.some((re) => re.test(merchant));
}

/** Spend is negative in this app, so its magnitude is what we report. */
export const spendOf = (t: SessionTransaction) =>
  t.amount < 0 && !isTransfer(t.merchant) ? -t.amount : 0;
export const incomeOf = (t: SessionTransaction) =>
  t.amount > 0 && !isTransfer(t.merchant) ? t.amount : 0;

export interface CategoryTotal {
  category: string;
  total: number;
  count: number;
  /** Share of all spend, 0..1. */
  share: number;
}

/** Spend per category, largest first. */
export function categoryTotals(txns: SessionTransaction[]): CategoryTotal[] {
  const totals = new Map<string, { total: number; count: number }>();
  for (const t of txns) {
    const spend = spendOf(t);
    if (spend === 0) continue;
    const entry = totals.get(t.category) ?? { total: 0, count: 0 };
    entry.total += spend;
    entry.count += 1;
    totals.set(t.category, entry);
  }
  const grand = [...totals.values()].reduce((s, e) => s + e.total, 0);
  return [...totals.entries()]
    .map(([category, e]) => ({
      category,
      total: e.total,
      count: e.count,
      share: grand > 0 ? e.total / grand : 0,
    }))
    .sort((a, b) => b.total - a.total);
}

export interface MerchantTotal {
  merchant: string;
  total: number;
  count: number;
}

/** Top merchants by spend — the concrete version of a category. */
export function topMerchants(
  txns: SessionTransaction[],
  limit = 8
): MerchantTotal[] {
  const totals = new Map<string, { total: number; count: number }>();
  for (const t of txns) {
    const spend = spendOf(t);
    if (spend === 0) continue;
    const entry = totals.get(t.merchant) ?? { total: 0, count: 0 };
    entry.total += spend;
    entry.count += 1;
    totals.set(t.merchant, entry);
  }
  return [...totals.entries()]
    .map(([merchant, e]) => ({ merchant, ...e }))
    .sort((a, b) => b.total - a.total)
    .slice(0, limit);
}

/** Calendar months covered, so a monthly average isn't divided by a guess. */
export function monthsCovered(txns: SessionTransaction[]): number {
  const months = new Set(txns.map((t) => t.occurredOn.slice(0, 7)));
  return Math.max(months.size, 1);
}

/**
 * Months in which money actually moved in the given direction.
 *
 * Files rarely cover the same window: a bank export going back to January
 * alongside a card statement covering June and July would divide two months of
 * card spending across seven, understating it by more than three times. Since
 * that average is what the ranking engine reads, each side is averaged over
 * the months it genuinely spans.
 */
function activeMonths(
  txns: SessionTransaction[],
  amount: (t: SessionTransaction) => number
): number {
  const months = new Set(
    txns.filter((t) => amount(t) > 0).map((t) => t.occurredOn.slice(0, 7))
  );
  return Math.max(months.size, 1);
}

export interface SessionSummary {
  totalSpend: number;
  totalIncome: number;
  monthlySpend: number;
  transactionCount: number;
  /** Calendar months any transaction falls in. */
  months: number;
  /** Months containing spending — the divisor behind `monthlySpend`. */
  spendMonths: number;
  /** Months containing income — the divisor behind `monthlyIncome`. */
  incomeMonths: number;
  monthlyIncome: number;
  topCategory: CategoryTotal | null;
  /** Total across cards that reported a limit; null when none did. */
  creditLimit: number | null;
  currentBalance: number | null;
  utilization: number | null;
  periodStart: string | null;
  periodEnd: string | null;
}

export function summarize(session: SessionState): SessionSummary {
  const txns = session.transactions;
  const totalSpend = txns.reduce((s, t) => s + spendOf(t), 0);
  const totalIncome = txns.reduce((s, t) => s + incomeOf(t), 0);
  const months = monthsCovered(txns);
  const spendMonths = activeMonths(txns, spendOf);
  const incomeMonths = activeMonths(txns, incomeOf);
  const cats = categoryTotals(txns);

  const withLimits = session.heldCards.filter(
    (c) => typeof c.creditLimit === "number" && c.creditLimit > 0
  );
  const creditLimit = withLimits.length
    ? withLimits.reduce((s, c) => s + (c.creditLimit ?? 0), 0)
    : null;
  const currentBalance = withLimits.length
    ? withLimits.reduce((s, c) => s + (c.currentBalance ?? 0), 0)
    : null;

  const dates = txns.map((t) => t.occurredOn).sort();

  return {
    totalSpend,
    totalIncome,
    monthlySpend: totalSpend / spendMonths,
    monthlyIncome: totalIncome / incomeMonths,
    transactionCount: txns.length,
    months,
    spendMonths,
    incomeMonths,
    topCategory: cats[0] ?? null,
    creditLimit,
    currentBalance,
    utilization:
      creditLimit && currentBalance != null
        ? Math.max(0, currentBalance) / creditLimit
        : null,
    periodStart: dates[0] ?? null,
    periodEnd: dates[dates.length - 1] ?? null,
  };
}

export interface Subscription {
  merchant: string;
  /** Typical charge — the median, so one price change doesn't skew it. */
  amount: number;
  /** How many charges we matched. */
  charges: number;
  /** Average days between charges. */
  cadenceDays: number;
  /** monthly | yearly | weekly, from the cadence. */
  period: "weekly" | "monthly" | "yearly";
  /** What this costs per month, normalized across periods. */
  monthlyCost: number;
  lastCharged: string;
  /** True when the amount never varies — the strongest subscription signal. */
  fixedAmount: boolean;
}

const DAY = 86_400_000;

/**
 * Payment rails that bill per order, never on a cycle.
 *
 * `DD*` is DoorDash, `TST*` is Toast, `SQ*` is Square, `CLV*` is Clover — food
 * ordering and card-present restaurant terminals. Eating at the same place
 * every Friday for the same amount produces a perfect cadence at a perfect
 * price, which is indistinguishable from a subscription by shape alone. It
 * isn't one: nothing renews, and there is nothing to cancel. Recognising the
 * rail settles it regardless of how many charges line up.
 */
const ORDER_RAIL_PREFIXES = [
  "DD",
  "TST",
  "SQ",
  "CLV",
  "SPO",
  "UEP",
  "GH",
  "PY",
  "SNACK",
  "CHECKLE",
] as const;

const FOOD_MERCHANT_HINTS = [
  "doordash",
  "toast",
  "grubhub",
  "ubereats",
  "uber eats",
  "seamless",
  "postmates",
  "caviar",
  "restaurant",
  "pizza",
  "cafe",
  "coffee",
  "kitchen",
  "grill",
  "bakery",
  "deli",
  "sushi",
] as const;

/** Categories where charges are per-purchase, not per-cycle. */
const NEVER_RECURRING_CATEGORIES = new Set(["dining", "groceries"]);

function isPerOrderSpend(merchant: string, category: string): boolean {
  if (NEVER_RECURRING_CATEGORIES.has(category)) return true;

  // A processor marker appears as a leading token followed by `*`.
  const marker = merchant.match(/^([A-Z]+)\s*\*/i)?.[1]?.toUpperCase();
  if (marker && (ORDER_RAIL_PREFIXES as readonly string[]).includes(marker)) {
    return true;
  }

  const lower = merchant.toLowerCase();
  return FOOD_MERCHANT_HINTS.some((hint) => lower.includes(hint));
}

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/**
 * Recurring charges, found by shape rather than by a merchant list.
 *
 * A subscription bills the same merchant, for near enough the same amount, on a
 * regular cadence. Matching that pattern catches services no keyword list would
 * know about, and avoids flagging a coffee shop visited weekly at varying
 * prices. Needs at least two charges, so a single month of statements will
 * surface little — the honest answer given the data rather than a guess.
 */
export function detectSubscriptions(txns: SessionTransaction[]): Subscription[] {
  const byMerchant = new Map<string, SessionTransaction[]>();
  for (const t of txns) {
    if (spendOf(t) === 0) continue;
    const list = byMerchant.get(t.merchant) ?? [];
    list.push(t);
    byMerchant.set(t.merchant, list);
  }

  const subs: Subscription[] = [];
  for (const [merchant, list] of byMerchant) {
    if (list.length < 2) continue;

    // Settle the payment rail before looking at shape at all: a restaurant
    // visited on a steady cadence for a steady amount matches every structural
    // test a subscription does, and is still not one.
    if (isPerOrderSpend(merchant, list[0].category)) continue;
    const sorted = [...list].sort((a, b) => a.occurredOn.localeCompare(b.occurredOn));
    const amounts = sorted.map(spendOf);
    const typical = median(amounts);
    if (typical <= 0) continue;

    // Amounts must cluster: a subscription's price is stable, a restaurant's
    // is not. 15% tolerance absorbs tax and FX drift without letting variable
    // spend through.
    const consistent = amounts.every((a) => Math.abs(a - typical) / typical <= 0.15);
    if (!consistent) continue;

    const gaps: number[] = [];
    for (let i = 1; i < sorted.length; i++) {
      gaps.push(
        (Date.parse(sorted[i].occurredOn) - Date.parse(sorted[i - 1].occurredOn)) / DAY
      );
    }
    const cadence = gaps.reduce((s, g) => s + g, 0) / gaps.length;
    if (cadence < 5) continue; // several charges in a week is not a subscription

    let period: Subscription["period"];
    let monthlyCost: number;
    if (cadence <= 10) {
      period = "weekly";
      monthlyCost = typical * (30 / 7);
    } else if (cadence <= 45) {
      period = "monthly";
      monthlyCost = typical;
    } else if (cadence <= 400) {
      period = "yearly";
      monthlyCost = typical / 12;
    } else {
      continue;
    }

    // Two charges alone are weak evidence: eating at the same place twice a
    // month for the same amount looks identical to a subscription. Three
    // charges establish a cadence on their own; with only two, require an
    // exactly repeated amount and a category where recurring billing is the
    // norm. Everyday-spend categories are excluded rather than guessed at —
    // a false subscription is worse than a missing one, because the whole
    // point of the list is that every row is worth cancelling.
    // Dining and groceries are excluded outright above; what remains here are
    // categories where recurring billing exists but is not the norm.
    const VOLATILE = new Set(["transport", "shopping", "travel"]);
    const category = sorted[0].category;
    // A weekly cadence inferred from two points is noise — two visits eight
    // days apart is a habit, not a billing cycle. So the two-charge case is
    // additionally restricted to the periods things are actually billed on.
    const exact = new Set(amounts.map((a) => a.toFixed(2))).size === 1;
    const weakEvidence =
      sorted.length < 3 &&
      !(exact && !VOLATILE.has(category) && period !== "weekly");
    if (weakEvidence) continue;

    subs.push({
      merchant,
      amount: typical,
      charges: sorted.length,
      cadenceDays: Math.round(cadence),
      period,
      monthlyCost,
      lastCharged: sorted[sorted.length - 1].occurredOn,
      fixedAmount: exact,
    });
  }

  return subs.sort((a, b) => b.monthlyCost - a.monthlyCost);
}

/** Monthly spend per calendar month, oldest first — the trend line. */
export function monthlyTrend(
  txns: SessionTransaction[]
): { month: string; spend: number; income: number }[] {
  const months = new Map<string, { spend: number; income: number }>();
  for (const t of txns) {
    const key = t.occurredOn.slice(0, 7);
    const e = months.get(key) ?? { spend: 0, income: 0 };
    e.spend += spendOf(t);
    e.income += incomeOf(t);
    months.set(key, e);
  }
  return [...months.entries()]
    .map(([month, e]) => ({ month, ...e }))
    .sort((a, b) => a.month.localeCompare(b.month));
}

/**
 * Cards shown as accounts. A held card is the only kind of account this app
 * has now that everything arrives by statement rather than by bank link.
 */
export function cardSpend(
  card: HeldCard,
  txns: SessionTransaction[]
): number {
  return txns
    .filter((t) => t.sourceId === card.id)
    .reduce((s, t) => s + spendOf(t), 0);
}

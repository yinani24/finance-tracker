/**
 * What the user actually earns, from the shape of their deposits.
 *
 * Averaging total income over the months a file spans is wrong whenever the
 * file reaches back further than the job does: a bank export covering January
 * to July, with payroll starting in May, reports a third of the real salary.
 * It is also wrong in the other direction — a partial final month drags the
 * average down.
 *
 * A salary has a cadence. Reading that cadence and multiplying by its periods
 * per year gives the figure a lender or a budget would use, and separates the
 * dependable part of income from interest, refunds and one-off deposits.
 */

import type { SessionTransaction } from "./types";
import { incomeOf } from "./derive";

export type Cadence =
  | "weekly"
  | "biweekly"
  | "semimonthly"
  | "monthly"
  | "quarterly"
  | "yearly"
  | "irregular";

export const PERIODS_PER_YEAR: Record<Exclude<Cadence, "irregular">, number> = {
  weekly: 52,
  biweekly: 26,
  semimonthly: 24,
  monthly: 12,
  quarterly: 4,
  yearly: 1,
};

export interface IncomeSource {
  merchant: string;
  /** Typical deposit — the median of recent ones, so a raise wins over history. */
  amount: number;
  deposits: number;
  cadence: Cadence;
  /** What this earns in a year, from cadence × amount. */
  annualized: number;
  firstSeen: string;
  lastSeen: string;
  /** True for a dependable, regularly-timed source — a salary rather than a refund. */
  isRecurring: boolean;
  /** True when the name itself says payroll, which the cadence then confirms. */
  looksLikePayroll: boolean;
}

export interface IncomeAnalysis {
  sources: IncomeSource[];
  /** Dependable income per month, from recurring sources only. */
  monthlyRecurring: number;
  /** Everything else, averaged over the period observed. */
  monthlyIrregular: number;
  monthlyTotal: number;
  annualTotal: number;
  primary: IncomeSource | null;
}

const DAY = 86_400_000;
const PAYROLL_HINTS =
  /\b(?:payroll|salary|direct\s*dep|dir\s*dep|paycheck|wages|payment\s+from)\b/i;

function median(xs: number[]): number {
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/**
 * Twice a month and every fourteen days look almost identical by gap alone —
 * roughly 15 days either way — but they pay 24 and 26 times a year, a
 * difference of two whole pay cheques.
 *
 * They are told apart by where in the month the money lands. A semi-monthly
 * schedule is anchored to dates (the 15th and the last day, say), so every
 * deposit clusters onto one of two days of the month. A fortnightly one is
 * anchored to a weekday instead, so it drifts through the month and the days
 * spread out.
 */
function isSemiMonthly(dates: string[]): boolean {
  const days = dates
    .map((d) => Number(d.slice(8, 10)))
    .sort((a, b) => a - b);

  // Month ends are the same anchor even though the number differs by month,
  // so 29, 30 and 31 must fall in one cluster — hence a tolerance rather than
  // exact equality.
  const TOLERANCE = 2;
  const clusters: number[][] = [];
  for (const day of days) {
    const last = clusters[clusters.length - 1];
    if (last && day - last[last.length - 1] <= TOLERANCE) last.push(day);
    else clusters.push([day]);
  }

  // A 1st-of-month deposit and a 31st are the same anchor seen from either end
  // of the calendar; merge them before counting.
  if (
    clusters.length > 1 &&
    clusters[0][0] <= TOLERANCE &&
    clusters[clusters.length - 1].at(-1)! >= 31 - TOLERANCE
  ) {
    clusters[0].push(...clusters.pop()!);
  }

  return clusters.length <= 2;
}

function cadenceOf(dates: string[]): Cadence {
  if (dates.length < 2) return "irregular";
  const sorted = [...dates].sort();
  const gaps: number[] = [];
  for (let i = 1; i < sorted.length; i++) {
    gaps.push((Date.parse(sorted[i]) - Date.parse(sorted[i - 1])) / DAY);
  }
  const gap = median(gaps);

  // Regularity matters as much as the average: deposits at 3, 40 and 12 days
  // average out to something monthly-looking without being monthly at all.
  const spread = Math.max(...gaps) - Math.min(...gaps);

  if (gap >= 5 && gap <= 9 && spread <= 4) return "weekly";
  if (gap >= 12 && gap <= 18 && spread <= 8) {
    return isSemiMonthly(sorted) ? "semimonthly" : "biweekly";
  }
  if (gap >= 26 && gap <= 35 && spread <= 12) return "monthly";
  if (gap >= 80 && gap <= 100) return "quarterly";
  if (gap >= 330 && gap <= 400) return "yearly";
  return "irregular";
}

export function analyzeIncome(txns: SessionTransaction[]): IncomeAnalysis {
  const byMerchant = new Map<string, SessionTransaction[]>();
  for (const t of txns) {
    if (incomeOf(t) === 0) continue;
    const list = byMerchant.get(t.merchant) ?? [];
    list.push(t);
    byMerchant.set(t.merchant, list);
  }

  const sources: IncomeSource[] = [];
  for (const [merchant, list] of byMerchant) {
    const sorted = [...list].sort((a, b) =>
      a.occurredOn.localeCompare(b.occurredOn)
    );
    const dates = sorted.map((t) => t.occurredOn);
    const cadence = cadenceOf(dates);

    // The most recent deposits describe current pay; older ones may predate a
    // raise. Three is enough to shrug off a single odd cheque.
    const recent = sorted.slice(-3).map(incomeOf);
    const amount = median(recent);

    // Two deposits can fall a fortnight apart by chance. A dependable source
    // needs three, so the cadence is observed rather than assumed.
    const isRecurring = cadence !== "irregular" && sorted.length >= 3;

    const total = sorted.reduce((s, t) => s + incomeOf(t), 0);
    // `isRecurring` already excludes the irregular case, so the cadence here
    // is always one with a known number of periods per year.
    const annualized = isRecurring
      ? amount * PERIODS_PER_YEAR[cadence as Exclude<Cadence, "irregular">]
      : total; // observed only; not projected forward

    sources.push({
      merchant,
      amount,
      deposits: sorted.length,
      cadence,
      annualized,
      firstSeen: dates[0],
      lastSeen: dates[dates.length - 1],
      isRecurring,
      looksLikePayroll: PAYROLL_HINTS.test(merchant),
    });
  }

  sources.sort((a, b) => b.annualized - a.annualized);

  const recurring = sources.filter((s) => s.isRecurring);
  const irregular = sources.filter((s) => !s.isRecurring);

  const monthlyRecurring = recurring.reduce((s, x) => s + x.annualized / 12, 0);

  // One-off deposits are averaged over the window they were seen in rather
  // than annualized, since there is no reason to expect them to repeat.
  const irregularTotal = irregular.reduce((s, x) => s + x.annualized, 0);
  const allDates = txns.map((t) => t.occurredOn).sort();
  const spanMonths = allDates.length
    ? Math.max(
        1,
        new Set(allDates.map((d) => d.slice(0, 7))).size
      )
    : 1;
  const monthlyIrregular = irregularTotal / spanMonths;

  const monthlyTotal = monthlyRecurring + monthlyIrregular;

  return {
    sources,
    monthlyRecurring,
    monthlyIrregular,
    monthlyTotal,
    annualTotal: monthlyTotal * 12,
    // The headline source is the biggest recurring one — a salary, not the
    // largest single deposit, which could be a tax refund.
    primary: recurring[0] ?? null,
  };
}

export function cadenceLabel(cadence: Cadence): string {
  switch (cadence) {
    case "weekly":
      return "weekly";
    case "biweekly":
      return "every two weeks";
    case "semimonthly":
      return "twice a month";
    case "monthly":
      return "monthly";
    case "quarterly":
      return "quarterly";
    case "yearly":
      return "yearly";
    default:
      return "irregular";
  }
}

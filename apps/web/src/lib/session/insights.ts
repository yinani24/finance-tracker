/**
 * Findings that cut across the other pages.
 *
 * The old Insights page wrapped the recommendation engine, so every item it
 * could produce ("apply for X", "card Y underperforms") already had a page of
 * its own. This version only emits what no single page can see: money leaking
 * through subscriptions, utilization dragging on a score, spend outrunning
 * income, and category spend sitting on the wrong held card.
 *
 * Pure functions over session state plus the per-category rates the portfolio
 * endpoint returns. Every insight carries the numbers it was derived from, so
 * a reader can check the claim rather than trust it.
 */

import type { SessionState } from "./types";
import {
  categoryTotals,
  detectSubscriptions,
  monthsCovered,
  spendOf,
  summarize,
  type Subscription,
} from "./derive";

export type InsightSeverity = "opportunity" | "warning" | "critical";

export interface Insight {
  id: string;
  title: string;
  body: string;
  /** Dollars per year this is worth, when that can be stated honestly. */
  impactAnnual: number | null;
  severity: InsightSeverity;
  effort: "low" | "medium" | "high";
  evidence: { label: string; value: string }[];
}

/** One category's assignment, as returned by /recommendations/portfolio/stateless. */
export interface CategoryAssignment {
  category: string;
  best_card: { name: string; issuer: string } | null;
  rate: number | null;
  rationale?: string;
  card_rates?: Record<string, number>;
}

const money = (n: number) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD" });

/** Utilization above this is the point it starts costing score meaningfully. */
const UTILIZATION_WARN = 0.3;
const UTILIZATION_CRITICAL = 0.5;

/** A subscription unseen for this long is worth a second look. */
const STALE_DAYS = 60;

function subscriptionInsights(
  subs: Subscription[],
  latest: string | null
): Insight[] {
  if (subs.length === 0) return [];
  const insights: Insight[] = [];
  const monthly = subs.reduce((s, x) => s + x.monthlyCost, 0);

  insights.push({
    id: "subscriptions-total",
    title: `${money(monthly)} a month goes to ${subs.length} recurring charge${subs.length === 1 ? "" : "s"}`,
    body: `That is ${money(monthly * 12)} a year committed before any discretionary spending. Recurring charges are the cheapest thing to cut because cancelling once ends the cost permanently.`,
    impactAnnual: monthly * 12,
    severity: "opportunity",
    effort: "low",
    evidence: subs.slice(0, 5).map((s) => ({
      label: s.merchant,
      value: `${money(s.amount)} ${s.period}`,
    })),
  });

  // A charge that stopped appearing is either cancelled already or billing on a
  // cycle longer than the statements loaded — worth surfacing, not asserting.
  if (latest) {
    const cutoff = Date.parse(latest) - STALE_DAYS * 86_400_000;
    const stale = subs.filter(
      (s) => s.period !== "yearly" && Date.parse(s.lastCharged) < cutoff
    );
    if (stale.length > 0) {
      const staleMonthly = stale.reduce((s, x) => s + x.monthlyCost, 0);
      insights.push({
        id: "subscriptions-stale",
        title: `${stale.length} subscription${stale.length === 1 ? " has" : "s have"} not been charged recently`,
        body: `No charge in the last ${STALE_DAYS} days of the statements loaded. Either it was already cancelled, or it bills on a longer cycle than the data covers.`,
        impactAnnual: staleMonthly * 12,
        severity: "opportunity",
        effort: "low",
        evidence: stale.map((s) => ({
          label: s.merchant,
          value: `last seen ${s.lastCharged}`,
        })),
      });
    }
  }

  return insights;
}

function utilizationInsight(session: SessionState): Insight | null {
  const { creditLimit, currentBalance, utilization } = summarize(session);
  if (utilization == null || creditLimit == null || currentBalance == null) {
    return null;
  }
  if (utilization < UTILIZATION_WARN) return null;

  const target = creditLimit * UTILIZATION_WARN;
  const payDown = currentBalance - target;

  return {
    id: "utilization",
    title: `Credit utilization is ${Math.round(utilization * 100)}%`,
    body:
      `Utilization is roughly 30% of a FICO score, and the scoring benefit falls off above 30%. ` +
      `Paying down ${money(payDown)} before the statement closes would bring it under that line.` +
      ` This affects approval odds on every card on the Recommendations page.`,
    // Deliberately null: the score effect is real but not a dollar figure we
    // can honestly compute, and inventing one would rank it against insights
    // whose numbers are actual.
    impactAnnual: null,
    severity: utilization >= UTILIZATION_CRITICAL ? "critical" : "warning",
    effort: "medium",
    evidence: [
      { label: "Balance", value: money(currentBalance) },
      { label: "Limit", value: money(creditLimit) },
      { label: "To reach 30%", value: `pay ${money(payDown)}` },
    ],
  };
}

function cashflowInsight(session: SessionState): Insight | null {
  const s = summarize(session);
  // Without income data there is nothing to compare against — the Income page
  // exists precisely because a card statement can't answer this.
  if (s.totalIncome <= 0) return null;

  const monthlyIncome = s.totalIncome / s.months;
  const net = monthlyIncome - s.monthlySpend;
  if (net >= 0) return null;

  return {
    id: "cashflow-negative",
    title: `Spending exceeds income by ${money(-net)} a month`,
    body: `Across the statements loaded, ${money(s.monthlySpend)} went out against ${money(monthlyIncome)} coming in. A rewards card cannot outrun this — the gap is worth more than any sign-up bonus.`,
    impactAnnual: net * 12,
    severity: "critical",
    effort: "high",
    evidence: [
      { label: "Monthly income", value: money(monthlyIncome) },
      { label: "Monthly spend", value: money(s.monthlySpend) },
      { label: "Months covered", value: String(s.months) },
    ],
  };
}

/**
 * Category spend sitting on a card that earns less than another card held.
 *
 * Only fires when the transactions are attributed to a card (they are, when
 * read from a statement) and the winning card is a different one.
 */
function wrongCardInsights(
  session: SessionState,
  assignments: CategoryAssignment[]
): Insight[] {
  if (session.heldCards.length < 2 || assignments.length === 0) return [];

  const months = monthsCovered(session.transactions);
  const nameById = new Map(session.heldCards.map((c) => [c.id, c.name]));
  const insights: Insight[] = [];

  for (const a of assignments) {
    const best = a.best_card?.name;
    const rates = a.card_rates;
    if (!best || !rates || a.rate == null) continue;

    // Spend in this category, grouped by the card it was actually charged to.
    const byCard = new Map<string, number>();
    for (const t of session.transactions) {
      if (t.category !== a.category || !t.sourceId) continue;
      const name = nameById.get(t.sourceId);
      if (!name || name === best) continue;
      byCard.set(name, (byCard.get(name) ?? 0) + spendOf(t));
    }

    for (const [usedCard, total] of byCard) {
      const usedRate = rates[usedCard];
      if (usedRate == null || usedRate >= a.rate) continue;

      const annualSpend = (total / months) * 12;
      const gain = (annualSpend * (a.rate - usedRate)) / 100;
      if (gain < 1) continue; // not worth a reader's attention

      insights.push({
        id: `wrong-card-${a.category}-${usedCard}`,
        title: `${a.category} spend is earning ${usedRate}% instead of ${a.rate}%`,
        body: `${money(annualSpend)} a year of ${a.category} is going on ${usedCard}, which earns ${usedRate}% there. ${best} earns ${a.rate}%. Moving it is a change of habit, not an application.`,
        impactAnnual: gain,
        severity: "opportunity",
        effort: "low",
        evidence: [
          { label: "On", value: `${usedCard} (${usedRate}%)` },
          { label: "Better", value: `${best} (${a.rate}%)` },
          { label: "Annual spend", value: money(annualSpend) },
        ],
      });
    }
  }

  return insights;
}

/**
 * A category taking a large share of spend that no held card rewards above the
 * base rate — the gap a new card would actually fill.
 */
function unrewardedCategoryInsight(
  session: SessionState,
  assignments: CategoryAssignment[]
): Insight | null {
  if (assignments.length === 0) return null;
  const cats = categoryTotals(session.transactions);
  const months = monthsCovered(session.transactions);

  for (const c of cats) {
    if (c.share < 0.15) break; // sorted desc; nothing below matters
    const a = assignments.find((x) => x.category === c.category);
    if (!a || a.rate == null || a.rate > 1.5) continue;

    // A rate of 0 across every held card means the card never matched the
    // dataset, not that it genuinely earns nothing. Claiming "earns only 0%"
    // off a failed lookup is worse than staying quiet.
    const rates = Object.values(a.card_rates ?? {});
    if (rates.length > 0 && rates.every((r) => r === 0)) continue;

    const annualSpend = (c.total / months) * 12;
    return {
      id: `unrewarded-${c.category}`,
      title: `${c.category} is ${Math.round(c.share * 100)}% of spending and earns only ${a.rate}%`,
      body: `${money(annualSpend)} a year runs through ${c.category}, and the best card you hold earns ${a.rate}% on it. This is the gap a new card would close — the Recommendations page ranks by exactly this kind of shortfall.`,
      // A 3% category card is the common upgrade; state the delta it implies.
      impactAnnual: (annualSpend * (3 - a.rate)) / 100,
      severity: "opportunity",
      effort: "medium",
      evidence: [
        { label: "Annual spend", value: money(annualSpend) },
        { label: "Best held rate", value: `${a.rate}%` },
        { label: "Share of spending", value: `${Math.round(c.share * 100)}%` },
      ],
    };
  }
  return null;
}

/**
 * Build the ranked list. Highest annual impact first; insights without a
 * dollar figure sort by severity so a critical warning is never buried.
 */
export function buildInsights(
  session: SessionState,
  assignments: CategoryAssignment[] = []
): Insight[] {
  const subs = detectSubscriptions(session.transactions);
  const dates = session.transactions.map((t) => t.occurredOn).sort();
  const latest = dates[dates.length - 1] ?? null;

  const all = [
    ...subscriptionInsights(subs, latest),
    utilizationInsight(session),
    cashflowInsight(session),
    ...wrongCardInsights(session, assignments),
    unrewardedCategoryInsight(session, assignments),
  ].filter((x): x is Insight => x !== null);

  const severityRank = { critical: 0, warning: 1, opportunity: 2 } as const;

  return all.sort((a, b) => {
    const aImpact = a.impactAnnual == null ? null : Math.abs(a.impactAnnual);
    const bImpact = b.impactAnnual == null ? null : Math.abs(b.impactAnnual);
    if (aImpact == null || bImpact == null) {
      if (severityRank[a.severity] !== severityRank[b.severity]) {
        return severityRank[a.severity] - severityRank[b.severity];
      }
      if (aImpact == null && bImpact == null) return 0;
      return aImpact == null ? -1 : 1;
    }
    return bImpact - aImpact;
  });
}

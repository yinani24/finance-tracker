/**
 * What the numbers mean, said in sentences.
 *
 * Every page here presents totals and lets the reader work out the story: that
 * travel is a third of their spending, that a fifth of it earns nothing, that
 * the subscriptions they forgot about cost more than the annual fee they are
 * worried about. That is work a person shouldn't have to do at a glance.
 *
 * These build plain-language sentences from the same derived values the tables
 * use, so the prose can never disagree with the figures beside it. Nothing is
 * asserted that the data doesn't support: each sentence is emitted only when
 * the facts behind it exist, and hedged wording is preferred over confident
 * wording when the sample is thin.
 */

import type { SessionState } from "./types";
import {
  categoryTotals,
  detectSubscriptions,
  summarize,
  topMerchants,
} from "./derive";
import { analyzeIncome, cadenceLabel } from "./income";

const money = (n: number) =>
  n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: n >= 100 ? 0 : 2,
  });

export interface Narrative {
  /** The one-line summary: what this person's spending looks like. */
  headline: string;
  /** Supporting observations, most useful first. Each stands alone. */
  points: string[];
  /** The single most valuable thing to do next, when there is one. */
  suggestion: string | null;
}

/** "two months" reads better than "2 months" in a sentence. */
const WORDS = [
  "zero", "one", "two", "three", "four", "five",
  "six", "seven", "eight", "nine", "ten",
];
const spell = (n: number) => (n <= 10 ? WORDS[n] : String(n));

export function buildNarrative(session: SessionState): Narrative {
  const txns = session.transactions;
  const s = summarize(session);
  const cats = categoryTotals(txns);
  const subs = detectSubscriptions(txns);
  const income = analyzeIncome(txns);
  const merchants = topMerchants(txns, 3);

  if (txns.length === 0) {
    return {
      headline: "Nothing loaded yet.",
      points: [],
      suggestion: "Drop a statement and this fills itself in.",
    };
  }

  const top = cats[0];
  const period =
    s.spendMonths > 1
      ? `over ${spell(s.spendMonths)} months`
      : "over a single statement";

  const headline = top
    ? `You spend about ${money(s.monthlySpend)} a month ${period}, and ${top.category} takes the largest share of it at ${Math.round(top.share * 100)}%.`
    : `You spend about ${money(s.monthlySpend)} a month ${period}.`;

  const points: string[] = [];

  // Where the money concentrates. Two categories covering most of the spending
  // is the difference between "get a category card" and "get a flat-rate card".
  if (cats.length >= 2) {
    const twoShare = cats[0].share + cats[1].share;
    if (twoShare > 0.5) {
      points.push(
        `${cats[0].category} and ${cats[1].category} together are ${Math.round(twoShare * 100)}% of everything you spend, which is concentrated enough that a card built for those two would beat a flat-rate one.`
      );
    } else {
      points.push(
        `Your spending is spread fairly evenly — no two categories account for even half of it, so a good flat-rate card may serve you better than chasing bonus categories.`
      );
    }
  }

  if (merchants.length > 0 && merchants[0].count > 2) {
    const m = merchants[0];
    points.push(
      `${m.merchant} alone accounts for ${money(m.total)} across ${m.count} charges.`
    );
  }

  if (subs.length > 0) {
    const monthly = subs.reduce((a, b) => a + b.monthlyCost, 0);
    points.push(
      `${spell(subs.length)} recurring ${subs.length === 1 ? "charge costs" : "charges cost"} you ${money(monthly)} a month — ${money(monthly * 12)} a year that renews whether or not you think about it.`
    );
  }

  if (income.primary) {
    const p = income.primary;
    points.push(
      `${p.merchant} deposits ${money(p.amount)} ${cadenceLabel(p.cadence)} — ${money(p.annualized)} a year reaching your account, after tax and deductions.`
    );
    const net = income.monthlyTotal - s.monthlySpend;
    if (net < 0) {
      points.push(
        `You are spending ${money(-net)} a month more than you bring in.`
      );
    } else if (income.monthlyTotal > 0) {
      points.push(
        `That leaves ${money(net)} a month after the spending above — ${Math.round((net / income.monthlyTotal) * 100)}% of what lands in your account.`
      );
    }
  }

  if (s.utilization != null && s.utilization > 0.3) {
    points.push(
      `You are using ${Math.round(s.utilization * 100)}% of your available credit, which is high enough to be holding your score down.`
    );
  }

  // The suggestion is deliberately singular. A list of things to do is a list
  // of things not done.
  let suggestion: string | null = null;
  if (s.spendMonths < 2) {
    suggestion =
      "Add another month or two of statements — recurring charges only become visible once they repeat.";
  } else if (income.sources.length === 0) {
    suggestion =
      "Add a bank statement and this can tell you whether the spending above is actually sustainable.";
  } else if (s.utilization != null && s.utilization > 0.3) {
    suggestion =
      "Paying the balance down below 30% of your limit is the fastest thing you can change here.";
  } else if (top) {
    suggestion = `Worth checking which card earns most on ${top.category}, since that is where most of your money goes.`;
  }

  return { headline, points, suggestion };
}

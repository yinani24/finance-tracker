/**
 * Shapes for the client-only session.
 *
 * Everything the user tells us — the cards they hold, their credit standing,
 * and every transaction parsed out of their statements — lives here, in the
 * browser, for the life of the tab. None of it is sent to the API or written
 * to a database. The server-side models remain in the repo for later, unused.
 */

export type ScoreBand = "excellent" | "good" | "fair" | "poor";

/** A card the user says they already hold. */
export interface HeldCard {
  id: string;
  /** Display label, e.g. "Chase Sapphire Preferred ••3146". */
  name: string;
  /**
   * The product name on its own, e.g. "Sapphire Preferred".
   *
   * The card dataset is keyed on product name + issuer, and the display label
   * carries an issuer prefix and the last four, so matching on `name` fails and
   * every earn rate comes back 0. Kept separate rather than parsed back out at
   * each call site.
   */
  productName?: string;
  issuer?: string;
  /** Credit limit, in dollars. Drives utilization. */
  creditLimit?: number;
  /** Current statement balance, in dollars. */
  currentBalance?: number;
}

export interface CreditStanding {
  scoreBand?: ScoreBand;
  /** Cards opened in the last 24 months — drives issuer velocity rules. */
  recentApplications?: number;
}

/** One transaction parsed from an uploaded statement. Never leaves the device. */
export interface SessionTransaction {
  id: string;
  occurredOn: string; // ISO date
  merchant: string;
  /** Negative = spend, positive = money in — the app-wide convention. */
  amount: number;
  category: string;
  /** Which held card / account this came from, if known. */
  sourceId?: string;
}

export interface ImportRecord {
  id: string;
  fileName: string;
  kind: "csv" | "pdf";
  added: number;
  errors: number;
  importedAt: string;
}

export type SessionStep = "welcome" | "credit" | "cards" | "upload" | "ready";

export interface SessionState {
  step: SessionStep;
  credit: CreditStanding;
  heldCards: HeldCard[];
  transactions: SessionTransaction[];
  imports: ImportRecord[];
}

export const EMPTY_SESSION: SessionState = {
  step: "welcome",
  credit: {},
  heldCards: [],
  transactions: [],
  imports: [],
};

/**
 * Total utilization across the cards the user reported. Utilization is roughly
 * 30% of a FICO score and is the strongest signal we can compute without a
 * bureau, so it is worth asking for the limit explicitly. Returns null when we
 * don't have enough to say anything honest.
 */
export function utilization(cards: HeldCard[]): number | null {
  const withLimits = cards.filter(
    (c) => typeof c.creditLimit === "number" && c.creditLimit > 0
  );
  if (withLimits.length === 0) return null;
  const limit = withLimits.reduce((s, c) => s + (c.creditLimit ?? 0), 0);
  const balance = withLimits.reduce((s, c) => s + (c.currentBalance ?? 0), 0);
  if (limit <= 0) return null;
  return balance / limit;
}

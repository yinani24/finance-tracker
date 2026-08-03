/**
 * Pull the account's own details out of a statement's text.
 *
 * A statement already states the card, the issuer, the credit limit and the
 * balance — so asking the user for them is redundant friction. Extracting them
 * means a file drop is the entire onboarding: upload, and we know the card and
 * the utilization without a single question.
 *
 * Everything here is best-effort. Any field that isn't confidently found comes
 * back undefined, and the UI asks for only those.
 */

export interface StatementMetadata {
  /** e.g. "Sapphire Preferred" */
  cardName?: string;
  /** e.g. "Chase" */
  issuer?: string;
  /** Total credit line, in dollars. */
  creditLimit?: number;
  /** Statement balance, in dollars. */
  currentBalance?: number;
  /** Last four of the account number, for labelling only. */
  last4?: string;
  /** Statement period, as printed. */
  periodStart?: string;
  periodEnd?: string;
  /** True when the amounts follow the credit-card convention (charges positive). */
  isCredit: boolean;
}

const ISSUERS: [RegExp, string][] = [
  [/\bchase\b/i, "Chase"],
  [/\bamerican express\b|\bamex\b/i, "American Express"],
  [/\bcapital one\b/i, "Capital One"],
  [/\bcitibank\b|\bciti\b/i, "Citi"],
  [/\bdiscover\b/i, "Discover"],
  [/\bwells fargo\b/i, "Wells Fargo"],
  [/\bbank of america\b/i, "Bank of America"],
  [/\bbarclays\b/i, "Barclays"],
  [/\bus bank\b|\bu\.s\. bank\b/i, "U.S. Bank"],
];

/** Product names that identify the card itself, longest-first so
 *  "Sapphire Reserve" wins over a bare "Sapphire". */
const PRODUCTS = [
  "Sapphire Reserve", "Sapphire Preferred", "Freedom Unlimited", "Freedom Flex",
  "Venture X", "Venture Rewards", "Quicksilver", "SavorOne", "Savor",
  "Platinum Card", "Gold Card", "Green Card", "Blue Cash Preferred",
  "Blue Cash Everyday", "Cash Magnet", "Double Cash", "Custom Cash",
  "Strata Premier", "Premier", "Prestige", "Altitude Reserve", "Altitude Go",
  "Active Cash", "Autograph", "Bilt Mastercard", "Amazon Prime Store",
  "Sapphire", "Freedom", "Platinum", "Gold",
];

function money(raw: string | undefined): number | undefined {
  if (!raw) return undefined;
  const n = Number(raw.replace(/[$,\s]/g, ""));
  return Number.isFinite(n) ? n : undefined;
}

export function parseStatementMetadata(text: string): StatementMetadata {
  const meta: StatementMetadata = { isCredit: false };

  for (const [re, name] of ISSUERS) {
    if (re.test(text)) {
      meta.issuer = name;
      break;
    }
  }

  for (const product of PRODUCTS) {
    // Word-boundary match so "Gold" doesn't fire on "Goldman".
    if (new RegExp(`\\b${product.replace(/ /g, "\\s+")}\\b`, "i").test(text)) {
      meta.cardName = product;
      break;
    }
  }

  // Issuers label the limit differently: Chase "Credit Access Line",
  // Amex "Credit Limit", others "Total Credit Line".
  const limit = text.match(
    /(?:credit\s+(?:access\s+)?line|credit\s+limit|total\s+credit\s+line)\D{0,20}([\d,]+(?:\.\d{2})?)/i
  );
  meta.creditLimit = money(limit?.[1]);

  const balance = text.match(
    /(?:new\s+balance|statement\s+balance|balance\s+due)\D{0,20}(-?[\d,]+\.\d{2})/i
  );
  meta.currentBalance = money(balance?.[1]);

  const last4 = text.match(
    /account\s*(?:number|#)?:?\s*(?:[x*•]{4}[\s-]*){0,3}(\d{4})\b/i
  );
  if (last4) meta.last4 = last4[1];

  const period = text.match(
    /(?:opening\/closing\s+date|statement\s+period|billing\s+period)\D{0,10}([\d/]{6,10})\s*[-–]\s*([\d/]{6,10})/i
  );
  if (period) {
    meta.periodStart = period[1];
    meta.periodEnd = period[2];
  }

  // A credit-card statement is identifiable by the vocabulary that only
  // appears on one: a credit line, a minimum payment, or a purchase APR. This
  // decides the amount-sign convention the parser must use.
  meta.isCredit =
    /credit\s+(?:access\s+)?line|credit\s+limit|minimum\s+payment|purchase\s+interest|available\s+credit/i.test(
      text
    );

  return meta;
}

/** Utilization implied by a single statement, when both figures were found. */
export function statementUtilization(meta: StatementMetadata): number | null {
  if (!meta.creditLimit || meta.creditLimit <= 0) return null;
  if (meta.currentBalance == null) return null;
  return Math.max(0, meta.currentBalance) / meta.creditLimit;
}

/** A human label for the account, from whatever was found. */
export function statementLabel(meta: StatementMetadata): string {
  const parts = [meta.issuer, meta.cardName].filter(Boolean);
  const base = parts.length ? parts.join(" ") : "Statement";
  return meta.last4 ? `${base} ••${meta.last4}` : base;
}

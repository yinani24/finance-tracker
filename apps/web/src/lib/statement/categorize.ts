/**
 * Keyless, offline transaction categorizer.
 *
 * Port of `apps/api/app/services/enrichment/rules.py` (`RulesProvider`).
 * Assigns an internal-taxonomy category from merchant-name keyword rules, with
 * a payment-processor fallback. No network, no secrets — it runs on the user's
 * device against a statement that never leaves it.
 */

import { extractProcessor, normalizeMerchant } from "./merchant";

export type Category =
  | "dining"
  | "groceries"
  | "travel"
  | "transport"
  | "bills"
  | "entertainment"
  | "health"
  | "shopping"
  | "income"
  | "other";

// Payment-processor token → category. The processor a charge is routed through
// is often a stronger signal than the merchant name: anything billed via Toast
// or SpotOn is a restaurant, even a local one we've never seen. Applied as a
// fallback AFTER the merchant keywords, so a known brand always wins.
const PROCESSOR_CATEGORIES: Record<string, Category> = {
  // restaurant point-of-sale systems
  TST: "dining", // Toast
  SPO: "dining", // SpotOn
  UEP: "dining",
  PY: "dining",
  SNACK: "dining", // Snackpass
  CHECKLE: "dining", // Checkle
  // food delivery
  DD: "dining", // DoorDash
  GH: "dining", // Grubhub
  // grocery delivery
  IC: "groceries", // Instacart
  // ride / mobility
  UBER: "transport",
  LYFT: "transport",
  BAYWHEE: "transport", // Bay Wheels
  SPIN: "transport",
  LIME: "transport",
  // generic card-present processors — usually food/retail; dining is the
  // dominant real-world case for these in a consumer statement.
  SQ: "dining", // Square
  CLV: "dining", // Clover
};

// Ordered merchant-keyword rules → internal taxonomy category. The first rule
// with a keyword that appears in the normalized merchant name wins, so more
// specific rules must come before broader ones (e.g. delivery dining before a
// bare "uber" → transport).
const RULES: ReadonlyArray<readonly [Category, readonly string[]]> = [
  // dining — includes food-delivery, which must beat "uber" (transport) below
  [
    "dining",
    [
      "doordash", "uber eats", "ubereats", "grubhub", "postmates", "seamless",
      "starbucks", "dunkin*", "peet*", "coffee", "cafe", "restaurant", "grill",
      "bistro", "kitchen", "diner", "eatery", "tavern", "pizzeria", "pizza",
      "burger", "taco", "sushi", "ramen", "thai", "chipotle", "mcdonald*",
      "wendy*", "panera", "chick-fil", "shake shack", "olive garden", "subway",
      "deli", "bakery", "steakhouse", "brewery", "pub",
      // seen in real statements
      "dough", "noodle", "dumpling", "boba", "juice", "creamery",
      "ice cream", "donut", "bagel", "sandwich", "kebab", "curry",
      "bbq", "wings", "poke", "chaat", "jalebi", "mongolian", "farms",
      "szechuan", "sichuan", "hunan", "taqueria", "in-n-out", "in n out",
      "pho", "banh", "biryani", "tandoor", "dosa", "halal", "gyro",
      "chicken", "seafood", "buffet", "eats", "food", "snack", "bar &",
    ],
  ],
  // groceries
  [
    "groceries",
    [
      "whole foods", "trader joe*", "safeway", "kroger", "aldi", "costco",
      "wegmans", "publix", "sprouts", "food lion", "heb", "giant", "grocery",
      "supermarket", "market", "mart", "instacart",
    ],
  ],
  // travel (air + lodging)
  [
    "travel",
    [
      "airline", "airlines", "airways", "flight",
      // carriers as they actually appear on statements (often name+digits)
      "american air*", "united air*", "delta air*", "alaska air*",
      "spirit air*", "hawaiian air*", "sun country*", "southwest air*",
      "lugless", "clear me", "tsa",
      "delta", "united",
      "southwest", "jetblue", "alaska air", "spirit air", "frontier",
      "hotel", "marriott", "hilton", "hyatt", "airbnb", "expedia", "booking.",
      "priceline", "resort", "motel", "inn ", "lodge",
    ],
  ],
  // transport (ground)
  [
    "transport",
    [
      "uber", "lyft", "shell", "chevron", "exxon", "mobil", "arco", "76 ",
      "bp ", "gas ", "fuel", "parking", "toll", "transit", "metro", "bart",
      "amtrak", "caltrain", "dmv", "rental car", "hertz", "enterprise rent",
      "maverik", "casey*", "kum & go", "quiktrip", "circle k", "speedway",
      "sinclair", "sunoco", "valero", "gas station",
    ],
  ],
  // bills / utilities / recurring
  [
    "bills",
    [
      "rent", "mortgage", "electric", "pg&e", "utility", "water district",
      "verizon", "at&t", "t-mobile", "sprint", "comcast", "xfinity",
      "spectrum", "internet", "wireless", "insurance", "geico", "state farm",
      "student loan", "loan pmt",
      // fees + billing services seen in real statements
      "interest charge", "annual membership fee", "late fee",
      "simple bills", "billing", "utilities",
    ],
  ],
  // entertainment / subscriptions
  [
    "entertainment",
    [
      "netflix", "spotify", "hulu", "disney+", "disney plus", "hbo", "max ",
      "youtube", "prime video", "apple music", "cinema", "movie", "theater",
      "amc ", "regal", "steam", "playstation", "xbox", "nintendo",
      "ticketmaster", "concert",
      // software / AI / SaaS subscriptions
      "anthropic", "claude.ai", "openai", "chatgpt", "github", "notion",
      "figma", "adobe", "dropbox", "icloud", "google one", "patreon",
      "substack", "medium", "audible", "kindle", "marcus theat", "marcus cor",
    ],
  ],
  // health / medical / fitness
  [
    "health",
    [
      "pharmacy", "cvs", "walgreens", "rite aid", "doctor", "medical",
      "dental", "dentist", "clinic", "hospital", "urgent care", "optometr",
      "gym", "fitness", "planet fit", "yoga", "pilates",
      // personal care
      "supercuts", "salon", "barber", "haircut", "spa", "nails",
    ],
  ],
  // shopping — broad, so kept late so category-specific stores win first
  [
    "shopping",
    [
      "amazon", "amzn", "target", "walmart", "best buy", "ebay", "etsy",
      "apple store",
      "nike", "adidas", "macy*", "nordstrom", "kohl*", "ikea", "home depot",
      "lowe*", "sephora", "ulta", "store", "shop",
      // seen in real statements
      "staples", "office depot", "books", "galleria", "mall",
      "outlet", "uniqlo", "zara", "h&m", "costco whse", "cvs pharmacy",
      "flower", "florist", "gift", "hardware", "supply",
    ],
  ],
  // income
  [
    "income",
    [
      "payroll", "salary", "direct dep", "direct deposit", "paycheck",
      "ach credit", "interest paid", "dividend", "refund", "reimburse",
    ],
  ],
];

/** Equivalent of Python's `re.escape` for the characters JS treats specially. */
function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\/\-]/g, "\\$&");
}

function isAlnum(ch: string): boolean {
  return /[a-z0-9]/i.test(ch);
}

/**
 * Compile keywords into one alternation matched on WORD BOUNDARIES.
 *
 * Plain substring matching produced false positives — `mobil` (the gas brand)
 * matched "Payment Thank You-**Mobil**e", filing card payments under transport.
 * A boundary is only added where the keyword's edge is alphanumeric, so entries
 * like `booking.` or `pg&e` still match. A trailing `*` marks a PREFIX keyword
 * — no closing boundary — for merchants that run a code straight onto the name
 * (`american air*` matches `AMERICAN AIR0011111111111`).
 */
export function compileKeywords(keywords: readonly string[]): RegExp {
  const parts: string[] = [];
  for (const raw of keywords) {
    let kw = raw.trim();
    if (!kw) continue;
    const prefixOnly = kw.endsWith("*");
    if (prefixOnly) kw = kw.slice(0, -1);
    const lead = isAlnum(kw[0]) ? "\\b" : "";
    const trail = prefixOnly ? "" : isAlnum(kw[kw.length - 1]) ? "\\b" : "";
    parts.push(`${lead}${escapeRegExp(kw)}${trail}`);
  }
  return new RegExp(parts.join("|"), "i");
}

const COMPILED_RULES: ReadonlyArray<readonly [Category, RegExp]> = RULES.map(
  ([category, keywords]) => [category, compileKeywords(keywords)] as const,
);

export interface CategoryResult {
  category: Category;
  confidence: number;
  /** Cleaned merchant name, lower-cased, or `null` when there is nothing left. */
  normalizedMerchant: string | null;
}

/**
 * Classify a raw merchant description.
 *
 * Precedence mirrors the server's `_categorize`:
 *   1. Known-merchant keywords (most specific).
 *   2. Payment-processor fallback — we don't recognise the merchant, but we
 *      know how the charge was routed (Toast/Square → a restaurant).
 *   3. `other`, so a transaction is never left uncategorized.
 *
 * Classification runs on the RAW merchant (keyword matching already sees
 * through processor prefixes, and keeps brand tokens like `amzn`).
 */
export function categorize(merchant: string | null | undefined): CategoryResult {
  const name = (merchant ?? "").toLowerCase();
  let category: Category = "other";
  let confidence = 0.3;

  const keywordHit = COMPILED_RULES.find(([, pattern]) => pattern.test(name));
  if (keywordHit) {
    category = keywordHit[0];
    confidence = 0.9;
  } else {
    const processor = extractProcessor(merchant);
    const viaProcessor = processor ? PROCESSOR_CATEGORIES[processor] : undefined;
    if (viaProcessor) {
      category = viaProcessor;
      confidence = 0.7;
    }
  }

  return {
    category,
    confidence,
    normalizedMerchant: normalizeMerchant(merchant).toLowerCase() || null,
  };
}

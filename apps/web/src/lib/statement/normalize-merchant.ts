/**
 * Lift the real merchant out of a raw card descriptor.
 *
 * Card networks record whatever the acquirer sent, which mixes the merchant
 * with a processor prefix, a booking or order reference, a support URL, a
 * phone number and a city/state. Left alone, the reference number makes every
 * charge look like a different company: four American Airlines tickets appear
 * as `AMERICAN AIR0017412354781`, `AMERICAN AIR0017412354782` and so on, so a
 * top-merchant list becomes a list of ticket numbers.
 *
 * The server has `app/services/merchant.py`, but its trailing-noise rules
 * assume the reference is space-separated (`\s+\d{3,}`), which misses the
 * glued `AIR0017412354781` form entirely. This is the stricter version.
 *
 * Normalization is for grouping and display only. Categorization still reads
 * the raw string, because the processor prefix it strips (`DD*`, `TST*`) is
 * often the strongest category signal available.
 */

/** Payment processors that wrap a *different* merchant. */
const PROCESSOR_PREFIX =
  /^\s*(?:sq|tst|sp|spo|pp|paypal|square|toast|clover|clv|wpy|dd|gh|venmo|cash\s?app|ic|uep|py|snack|checkle)\s*\*\s*/i;

/** Domains and support URLs appended by online merchants. */
const URL_NOISE = /\b(?:[a-z0-9-]+\.)+(?:com|net|org|co|io)(?:\/[^\s]*)?/gi;

/** A booking, order or ticket reference: four or more digits in a row, glued
 *  to letters or not. */
const REFERENCE = /\b[a-z]*\d{4,}[a-z0-9]*\b/gi;

const PHONE = /\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g;

/** A trailing two-letter state code. */
const TRAILING_STATE = /\s+[A-Z]{2}\s*$/i;

/**
 * Cities common enough in card descriptors to be worth removing once a state
 * code has confirmed the tail is a location.
 *
 * Deliberately a short list rather than a gazetteer: a wrong removal renames a
 * merchant, and the state code alone already does most of the work. Anything
 * not listed simply stays, which is untidy but never wrong.
 */
const TRAILING_CITY = new RegExp(
  "\\s+(?:" +
    [
      "new york", "los angeles", "san francisco", "san jose", "san diego",
      "seattle", "portland", "chicago", "houston", "dallas", "austin",
      "fort worth", "phoenix", "denver", "boston", "atlanta", "miami",
      "philadelphia", "washington", "las vegas", "detroit", "minneapolis",
      "sunnyvale", "mountain view", "palo alto", "santa clara", "berkeley",
      "oakland", "cupertino", "redmond", "bellevue",
    ].join("|") +
    ")\\s*$",
  "i"
);

/** Noise words left behind once references and URLs are gone. */
const FILLER = /\b(?:help|support|bill|www|http|https)\b/gi;

/**
 * Cleaned names that mean the same company.
 *
 * Matched against the normalized string, longest key first, so "uber eats"
 * wins over "uber". Only entries where the raw form is genuinely unreadable
 * are listed — this is not meant to become a directory of every merchant.
 */
const BRANDS: [RegExp, string][] = [
  [/^uber\s*eats\b/i, "Uber Eats"],
  [/^uber\b/i, "Uber"],
  [/^lyft\b/i, "Lyft"],
  [/^american\s+air/i, "American Airlines"],
  [/^delta\s+air/i, "Delta Air Lines"],
  [/^united\s+air/i, "United Airlines"],
  [/^southwest\s+air/i, "Southwest Airlines"],
  [/^alaska\s+air/i, "Alaska Airlines"],
  [/^jetblue\b/i, "JetBlue"],
  [/^amazon\s+(?:mktpl|mktplace|marketplace|retail|prime)/i, "Amazon"],
  [/^amzn\b/i, "Amazon"],
  // Amazon stamps several descriptor shapes — "AMAZON MKTPL*", "Amazon.com*",
  // "AMZN Mktp" — all of which are the same merchant.
  [/^amazon(?:\.com)?\b/i, "Amazon"],
  [/^costco\s+by\s+instacar/i, "Costco (Instacart)"],
  [/^instacart\b/i, "Instacart"],
  [/^doordash\b/i, "DoorDash"],
  [/^grubhub\b/i, "Grubhub"],
  [/^trader\s*joe/i, "Trader Joe's"],
  [/^whole\s*foods/i, "Whole Foods"],
  [/^starbucks\b/i, "Starbucks"],
  [/^netflix\b/i, "Netflix"],
  [/^spotify\b/i, "Spotify"],
];

/** Words that stay upper-case rather than being title-cased. */
const KEEP_UPPER = new Set(["US", "USA", "UK", "NYC", "LA", "SF", "TV", "ATM"]);

function titleCase(text: string): string {
  return text
    .toLowerCase()
    .split(" ")
    .map((word) => {
      const upper = word.toUpperCase();
      if (KEEP_UPPER.has(upper)) return upper;
      // Capitalize after a hyphen too, so "7-ELEVEN" is not left as
      // "7-eleven" just because the first character is a digit.
      return word.replace(/(^|-)([a-z])/g, (_, sep, ch) => sep + ch.toUpperCase());
    })
    .join(" ");
}

/**
 * The processor token a descriptor was stamped with (`DD`, `TST`, `SQ`…),
 * or null. Kept because a charge through Toast is a restaurant even when the
 * restaurant itself is unrecognizable.
 */
export function extractProcessor(raw: string): string | null {
  const m = /^\s*([A-Za-z]{2,8})\s*\*/.exec(raw ?? "");
  return m ? m[1].toUpperCase() : null;
}

export function normalizeMerchant(raw: string): string {
  const original = (raw ?? "").trim();
  if (!original) return "";

  // Brands are matched against the raw descriptor first. Reference stripping
  // removes "AIR0017412354781" as one token, taking the "AIR" that identifies
  // the airline with it — so by the time the string is clean, "AMERICAN" alone
  // is left, which must not be confused with American Express.
  // The `*` a brand stamps before its own sub-product ("UBER *EATS") is a
  // separator, not part of either name, so it becomes whitespace for matching.
  const rawCleaned = original
    .replace(PROCESSOR_PREFIX, "")
    .replace(/\*/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  for (const [pattern, name] of BRANDS) {
    if (pattern.test(rawCleaned)) return name;
  }

  let s = original;
  s = s.replace(PROCESSOR_PREFIX, "");
  s = s.replace(URL_NOISE, " ");
  s = s.replace(PHONE, " ");
  s = s.replace(REFERENCE, " ");
  s = s.replace(FILLER, " ");
  s = s.replace(/[*#]+/g, " ");
  s = s.replace(/\s+/g, " ").trim();

  // Drop a trailing state code, then any city left dangling before it. Done
  // after reference removal so "FORT WORTH TX" isn't protected by the digits
  // that used to precede it.
  s = s.replace(TRAILING_STATE, "").trim();
  s = s.replace(TRAILING_CITY, "").trim();
  // A bare state code is all that's left when the descriptor was nothing but a
  // reference number and a location — there is no merchant name in it to find.
  if (/^[A-Za-z]{2}$/.test(s)) s = "";

  // Everything looked like noise — keep the original rather than invent a name
  // from whatever fragment survived.
  if (!s) return original;

  for (const [pattern, name] of BRANDS) {
    if (pattern.test(s)) return name;
  }

  // Mixed-case input is usually already human-readable; only shout-case
  // descriptors need converting.
  return s === s.toUpperCase() ? titleCase(s) : s;
}

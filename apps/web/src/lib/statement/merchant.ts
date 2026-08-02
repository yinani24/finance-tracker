/**
 * Merchant-name normalization — the base layer shared by every ingestion path.
 *
 * Port of `apps/api/app/services/merchant.py`.
 *
 * Raw transaction descriptions arrive wrapped in payment-processor prefixes
 * (`SQ *`, `TST*`, `PP*` …) and trailing location/phone noise. Left as-is, the
 * real merchant is hidden, so keyword categorization mislabels them (e.g.
 * `SQ *COFFEE BAR` never matches `coffee` → lands in `other`).
 */

// Pure payment-processor prefixes that wrap a *different* real merchant. Only
// these are stripped — NOT brand names like Amazon/Google/Apple/Uber, where the
// "prefix" IS the merchant and removing it would lose the name.
const PREFIX =
  /^\s*(?:sq ?\*|tst ?\*|sp ?\*|pp ?\*|paypal ?\*|square ?\*|toast ?\*|clover ?\*|clv ?\*|wpy ?\*|dd ?\*|gh ?\*|venmo ?\*|cash ?app ?\*)\s*/i;
/** The leading `<TOKEN>*` marker a processor stamps before the real merchant. */
const PROCESSOR_TOKEN = /^\s*([A-Za-z]{2,8})\s*\*/;
// Trailing noise: a phone number, then a 2-letter state code, then a store #.
// `g` where the Python counterpart is unanchored, because `re.sub` replaces
// every occurrence while `String.replace` would only replace the first.
const TRAIL_PHONE = /\s+\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b/g;
const TRAIL_STATE = /\s+[A-Za-z]{2}$/;
const TRAIL_STORE = /\s+#?\d{3,}\b/g;
const WS = /\s+/g;

/**
 * Return the leading payment-processor token (`SQ`, `TST`, `DD` …).
 *
 * Card networks record `<PROCESSOR>*<REAL MERCHANT>`, so the processor is often
 * a stronger category signal than the merchant name: a charge through Toast is
 * a restaurant even when we've never heard of the restaurant. Returns the
 * upper-cased token, or `null` when there is no `*` marker.
 */
export function extractProcessor(raw: string | null | undefined): string | null {
  const m = PROCESSOR_TOKEN.exec(raw ?? "");
  return m ? m[1].toUpperCase() : null;
}

/**
 * Return a cleaned merchant name: processor prefix + trailing phone/state/
 * store-number noise removed and whitespace collapsed.
 *
 * Conservative — if stripping would empty the string, the original (trimmed) is
 * kept so we never lose the merchant entirely.
 */
export function normalizeMerchant(raw: string | null | undefined): string {
  const original = (raw ?? "").trim();
  if (!original) return "";
  let s = original.replace(PREFIX, "");
  s = s.replace(TRAIL_PHONE, "");
  s = s.replace(TRAIL_STATE, "");
  s = s.replace(TRAIL_STORE, "");
  s = s.replace(WS, " ").trim();
  return s || original;
}

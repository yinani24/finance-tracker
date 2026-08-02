/**
 * PDF bank/card statement parsing, entirely in the browser.
 *
 * Port of the **heuristic** half of `apps/api/app/services/statement_pdf.py`.
 * The server implementation falls back to an LLM when the heuristic finds
 * nothing; that fallback is deliberately NOT ported — uploading the statement
 * to a model would defeat the point of parsing on-device. When the heuristic
 * finds nothing we return an empty result plus an error the UI can show.
 *
 * Text is extracted with `pdfjs-dist`, whose per-glyph runs are reassembled
 * into lines so the date-led-line heuristic sees the same shape of text that
 * `pdfplumber.extract_text()` produces server-side.
 */

import { parseAmount, parseDate } from "./parse-csv";
import { ParsedRow, ParseResult, RowError, StatementParseError } from "./types";

// A line that begins with a transaction date. Handles full dates (MM/DD/YY,
// YYYY-MM-DD) and the bare MM/DD that credit-card statements (e.g. Chase) use.
const LINE_DATE =
  /^\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}\/\d{1,2})\s+(.+)$/;
// A currency amount: optional $, thousands separators, 2 decimals, optional
// leading/trailing minus or accounting parentheses.
const MONEY = /-?\(?\$?\d[\d,]*\.\d{2}\)?-?/g;
// A full date anywhere in the text, used to infer the year for bare MM/DD rows.
const ANY_FULL_DATE = /\b\d{1,2}[/-]\d{1,2}[/-](\d{2,4})\b/;

/**
 * Best-effort statement year, to fill in bare `MM/DD` rows. Uses the first full
 * date found (e.g. an Opening/Closing date), normalizing 2-digit years.
 */
export function inferYear(text: string): number | null {
  const m = ANY_FULL_DATE.exec(text);
  if (!m) return null;
  const year = Number(m[1]);
  return year < 100 ? 2000 + year : year;
}

/**
 * Parse transactions from date-led statement lines.
 *
 * For each line beginning with a date, the LAST money amount on the line is the
 * transaction amount (statement descriptions can contain digits/phone numbers,
 * but the amount is the trailing column). Bare `MM/DD` dates get the statement
 * year inferred. `flipSign` inverts the sign for credit cards, whose statements
 * list purchases as positive and payments/credits as negative — the opposite of
 * our `negative = spend` convention.
 */
export function heuristicRows(text: string, flipSign = false): ParseResult {
  const year = inferYear(text);
  const rows: ParsedRow[] = [];
  for (const line of text.split(/\r\n|\r|\n/)) {
    const m = LINE_DATE.exec(line);
    if (!m) continue;
    const rest = m[2];
    const money = [...rest.matchAll(MONEY)];
    if (money.length === 0) continue;
    const last = money[money.length - 1];
    let amountToken = last[0];
    // trailing-minus convention (e.g. "12.65-") → negative
    if (amountToken.endsWith("-")) {
      amountToken = "-" + amountToken.slice(0, -1);
    }
    const description = rest.slice(0, last.index ?? 0).trim() || "Unknown";
    let dateStr = m[1];
    // A bare MM/DD (credit-card style) gets the inferred statement year.
    if (countOf(dateStr, "/") === 1 && countOf(dateStr, "-") === 0) {
      if (year === null) continue;
      dateStr = `${dateStr}/${year}`;
    }
    let occurredOn: string;
    let signedAmount: number;
    try {
      occurredOn = parseDate(dateStr);
      signedAmount = parseAmount(amountToken);
    } catch (exc) {
      if (exc instanceof RangeError) continue;
      throw exc;
    }
    if (flipSign) signedAmount = -signedAmount;
    rows.push({ occurredOn, merchant: description, signedAmount });
  }
  return { rows, errors: [] };
}

function countOf(haystack: string, needle: string): number {
  return haystack.split(needle).length - 1;
}

// --- pdfjs-dist text extraction ------------------------------------------

/** The slice of a pdfjs text item we depend on. */
interface TextItemLike {
  str?: string;
  transform?: number[];
  width?: number;
  hasEOL?: boolean;
}

/**
 * Reassemble pdfjs's positioned text runs into newline-separated lines.
 *
 * pdfjs hands back independently-positioned runs with no notion of a line, so
 * we bucket by baseline (`transform[5]`), order each bucket left-to-right by
 * `transform[4]`, and insert a space wherever there is a visible horizontal
 * gap. Without this the date-led-line heuristic has nothing to anchor on.
 */
export function itemsToLines(items: readonly TextItemLike[]): string {
  const placed = items
    .filter((it) => typeof it.str === "string" && it.str !== "")
    .map((it) => ({
      text: it.str as string,
      x: it.transform?.[4] ?? 0,
      y: it.transform?.[5] ?? 0,
      width: it.width ?? 0,
    }));
  if (placed.length === 0) return "";

  // Bucket by baseline with a small tolerance — glyph runs on one visual line
  // can differ by a fraction of a point.
  const TOLERANCE = 2;
  const buckets: { y: number; parts: typeof placed }[] = [];
  for (const item of [...placed].sort((a, b) => b.y - a.y)) {
    const bucket = buckets[buckets.length - 1];
    if (bucket && Math.abs(bucket.y - item.y) <= TOLERANCE) {
      bucket.parts.push(item);
    } else {
      buckets.push({ y: item.y, parts: [item] });
    }
  }

  return buckets
    .map(({ parts }) => {
      const ordered = parts.sort((a, b) => a.x - b.x);
      let line = "";
      let cursor: number | null = null;
      for (const part of ordered) {
        if (cursor !== null && part.x - cursor > 1 && !line.endsWith(" ")) {
          line += " ";
        }
        line += part.text;
        cursor = part.x + part.width;
      }
      return line.trim();
    })
    .filter((line) => line !== "")
    .join("\n");
}

let pdfjsPromise: Promise<typeof import("pdfjs-dist")> | null = null;

/**
 * Load pdfjs and point it at its worker.
 *
 * `GlobalWorkerOptions.workerSrc` must be set before the first `getDocument`,
 * and it must resolve to a real asset URL in the client bundle. `new URL(…,
 * import.meta.url)` is the form Next's bundler rewrites into an emitted asset
 * URL; a bare `"pdfjs-dist/build/pdf.worker.min.mjs"` string would be shipped
 * verbatim and 404 at runtime. Loading is deferred to first use so pdfjs (a
 * large dependency) stays out of the initial bundle and off the server.
 */
async function loadPdfjs(): Promise<typeof import("pdfjs-dist")> {
  if (!pdfjsPromise) {
    pdfjsPromise = (async () => {
      const pdfjs = await import("pdfjs-dist");
      pdfjs.GlobalWorkerOptions.workerSrc = new URL(
        "pdfjs-dist/build/pdf.worker.min.mjs",
        import.meta.url,
      ).toString();
      return pdfjs;
    })();
  }
  return pdfjsPromise;
}

/**
 * Extract text from a PDF's pages. Throws `StatementParseError` if the file
 * isn't a readable PDF or yields no extractable text (e.g. a scanned image,
 * which would need OCR).
 */
export async function extractText(pdfBytes: Uint8Array): Promise<string> {
  const pdfjs = await loadPdfjs();
  const pages: string[] = [];
  // pdfjs takes ownership of the buffer it is handed, so give it a copy.
  const task = pdfjs.getDocument({ data: new Uint8Array(pdfBytes) });
  try {
    const doc = await task.promise;
    for (let pageNo = 1; pageNo <= doc.numPages; pageNo++) {
      const page = await doc.getPage(pageNo);
      const content = await page.getTextContent();
      pages.push(itemsToLines(content.items as TextItemLike[]));
    }
  } catch (exc) {
    if (exc instanceof StatementParseError) throw exc;
    throw new StatementParseError("could not read PDF file");
  } finally {
    // Tear the worker down either way, so a rejected file doesn't leak one.
    await task.destroy();
  }

  const text = pages.join("\n").trim();
  if (!text) {
    throw new StatementParseError(
      "no extractable text in PDF (a scanned/image statement would need OCR)",
    );
  }
  return text;
}

/**
 * Reason surfaced when the heuristic recognises no transaction lines.
 *
 * The server falls back to an LLM here; we deliberately do not — sending the
 * statement anywhere would defeat on-device parsing — so the UI gets a clear
 * message instead of a silent empty result.
 */
export const NO_ROWS_REASON =
  "no transactions recognised in this PDF — the layout isn't one we can read " +
  "automatically. Try exporting the statement as CSV instead.";

/**
 * Run the heuristic over already-extracted statement text, turning "found
 * nothing" into an explicit error rather than a silently empty result.
 */
export function rowsFromText(text: string, isCredit = false): ParseResult {
  const { rows, errors } = heuristicRows(text, isCredit);
  if (rows.length === 0) {
    const noRows: RowError = { row: 0, reason: NO_ROWS_REASON };
    return { rows: [], errors: [...errors, noRows] };
  }
  return { rows, errors };
}

/**
 * Parse a PDF statement into `ParsedRow`s + per-row errors, mirroring
 * `parseCsv` so the rest of the pipeline is identical.
 *
 * `isCredit` flips the amount sign for credit-card statements.
 *
 * Throws `StatementParseError` for whole-file failures (empty file, unreadable
 * PDF, no extractable text).
 */
export async function parsePdf(
  pdfBytes: Uint8Array,
  isCredit = false,
): Promise<ParseResult> {
  // Matches the server's `not pdf_bytes.strip()`: all-whitespace is "empty".
  const WHITESPACE = new Set([0x20, 0x09, 0x0a, 0x0b, 0x0c, 0x0d]);
  if (pdfBytes.every((byte) => WHITESPACE.has(byte))) {
    throw new StatementParseError("file is empty");
  }
  return rowsFromText(await extractText(pdfBytes), isCredit);
}

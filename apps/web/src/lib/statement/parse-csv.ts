/**
 * Manual bank-statement import (CSV), running entirely in the browser.
 *
 * Port of `apps/api/app/services/statement_import.py`. Parses a statement CSV
 * export into `ParsedRow`s using the same header-alias matching, currency
 * parsing and date formats as the server implementation, so behaviour is
 * identical on either side.
 *
 * Amount convention: the CSV `amount` column is read as **negative = money out
 * (spend), positive = money in (income)**. Banks vary here; a bank that exports
 * two magnitude columns (debit/credit) instead of one signed column is handled
 * explicitly.
 */

import { ParsedRow, ParseResult, RowError, StatementParseError } from "./types";

// Header aliases matched case-insensitively (substring) against the CSV's
// column names. Order matters — see `matchColumn`.
const DATE_HINTS = ["date"] as const;
const DESC_HINTS = [
  "description",
  "merchant",
  "name",
  "payee",
  "memo",
  "details",
] as const;
/** A single signed-amount column (negative = spend). */
const AMOUNT_HINTS = ["amount", "value"] as const;
/** Some banks export two magnitude columns instead of one signed column. */
const DEBIT_HINTS = ["debit", "withdrawal"] as const;
const CREDIT_HINTS = ["credit", "deposit"] as const;

const MONTH_ABBR = [
  "jan",
  "feb",
  "mar",
  "apr",
  "may",
  "jun",
  "jul",
  "aug",
  "sep",
  "oct",
  "nov",
  "dec",
];

// Sub-patterns mirroring CPython's `_strptime` directive regexes, so the set of
// strings we accept (and reject) matches the server exactly.
const RE_Y = String.raw`\d{4}`; // %Y
const RE_y = String.raw`\d\d`; // %y
const RE_m = String.raw`1[0-2]|0[1-9]|[1-9]`; // %m
const RE_d = String.raw`3[01]|[12]\d|0[1-9]|[1-9]`; // %d
const RE_b = MONTH_ABBR.join("|"); // %b (matched case-insensitively)

type DateFields = { year: number; month: number; day: number };

interface DateFormat {
  pattern: RegExp;
  build: (groups: string[]) => DateFields;
}

/**
 * Python's two-digit-year rule (`_strptime`): 0-68 → 2000s, 69-99 → 1900s.
 */
function expandTwoDigitYear(value: number): number {
  return value <= 68 ? 2000 + value : 1900 + value;
}

function fmt(
  source: string,
  build: (groups: string[]) => DateFields,
): DateFormat {
  // CPython turns whitespace in the format string into `\s+` and anchors the
  // match at the start, then rejects any unconsumed trailing input — hence the
  // explicit `^`/`$` here.
  return { pattern: new RegExp(`^${source}$`, "i"), build };
}

// Same order as `_DATE_FORMATS` in the Python module. Order is load-bearing:
// `07/08/2026` resolves as %m/%d/%Y (8 July), not %d/%m/%Y.
const DATE_FORMATS: DateFormat[] = [
  // %Y-%m-%d
  fmt(`(${RE_Y})-(${RE_m})-(${RE_d})`, (g) => ({
    year: +g[0],
    month: +g[1],
    day: +g[2],
  })),
  // %m/%d/%Y
  fmt(`(${RE_m})/(${RE_d})/(${RE_Y})`, (g) => ({
    year: +g[2],
    month: +g[0],
    day: +g[1],
  })),
  // %m/%d/%y
  fmt(`(${RE_m})/(${RE_d})/(${RE_y})`, (g) => ({
    year: expandTwoDigitYear(+g[2]),
    month: +g[0],
    day: +g[1],
  })),
  // %d/%m/%Y
  fmt(`(${RE_d})/(${RE_m})/(${RE_Y})`, (g) => ({
    year: +g[2],
    month: +g[1],
    day: +g[0],
  })),
  // %m-%d-%Y
  fmt(`(${RE_m})-(${RE_d})-(${RE_Y})`, (g) => ({
    year: +g[2],
    month: +g[0],
    day: +g[1],
  })),
  // %Y/%m/%d
  fmt(`(${RE_Y})/(${RE_m})/(${RE_d})`, (g) => ({
    year: +g[0],
    month: +g[1],
    day: +g[2],
  })),
  // "%b %d, %Y"
  fmt(String.raw`(${RE_b})\s+(${RE_d}),\s+(${RE_Y})`, (g) => ({
    year: +g[2],
    month: MONTH_ABBR.indexOf(g[0].toLowerCase()) + 1,
    day: +g[1],
  })),
  // "%d %b %Y"
  fmt(String.raw`(${RE_d})\s+(${RE_b})\s+(${RE_Y})`, (g) => ({
    year: +g[2],
    month: MONTH_ABBR.indexOf(g[1].toLowerCase()) + 1,
    day: +g[0],
  })),
];

function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

function toIsoDate({ year, month, day }: DateFields): string {
  const yyyy = String(year).padStart(4, "0");
  const mm = String(month).padStart(2, "0");
  const dd = String(day).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

/**
 * Parse a date string into an ISO `YYYY-MM-DD` calendar date.
 *
 * Tries each supported format in priority order, exactly like the server's
 * `datetime.strptime` loop. Throws `RangeError` when nothing matches so the
 * caller can skip that row.
 */
export function parseDate(raw: string | null | undefined): string {
  const text = (raw ?? "").trim();
  if (!text) throw new RangeError("empty date");
  for (const format of DATE_FORMATS) {
    const m = format.pattern.exec(text);
    if (!m) continue;
    const fields = format.build(m.slice(1));
    // `datetime(...)` would reject e.g. 02/30, so we validate too rather than
    // silently rolling over into the next month.
    if (fields.day > daysInMonth(fields.year, fields.month)) continue;
    return toIsoDate(fields);
  }
  throw new RangeError(`unrecognized date format: '${text}'`);
}

// Accepts what Python's `float()` accepts for realistic statement values
// (optional sign, digits with an optional decimal point, optional exponent).
const NUMERIC = /^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$/;

/**
 * Parse a currency string into a number (negative = spend).
 *
 * Tolerates `$`/currency symbols, thousands separators, whitespace, and
 * accounting-style parentheses (`(50.00)` → `-50.00`). Throws `RangeError` on
 * an empty or non-numeric value so the caller can skip that row.
 */
export function parseAmount(raw: string | null | undefined): number {
  let text = (raw ?? "").trim();
  if (!text) throw new RangeError("empty amount");
  let negative = false;
  if (text.startsWith("(") && text.endsWith(")")) {
    negative = true;
    text = text.slice(1, -1);
  }
  text = text.split("$").join("").split(",").join("").split(" ").join("");
  if (!text) throw new RangeError("empty amount");
  if (!NUMERIC.test(text)) {
    throw new RangeError(`could not convert string to float: '${text}'`);
  }
  const value = Number(text);
  return negative ? -value : value;
}

/**
 * Like `parseAmount` but treats an empty cell as `0`.
 *
 * Used for two-column debit/credit layouts where a given row populates only
 * one of the two columns.
 */
function parseAmountOrZero(raw: string | null | undefined): number {
  if (!(raw ?? "").trim()) return 0;
  return parseAmount(raw);
}

/**
 * Return the column best matching `hints`, honoring hint priority.
 *
 * Hints are tried in order, so a higher-priority hint wins even if a
 * lower-priority one appears earlier among the columns (e.g. `Description`
 * beats a `Details` transaction-type column).
 */
export function matchColumn(
  fieldnames: readonly string[],
  hints: readonly string[],
): string | null {
  const normalized = fieldnames.map(
    (name) => [name, (name ?? "").trim().toLowerCase()] as const,
  );
  for (const hint of hints) {
    for (const [name, norm] of normalized) {
      if (norm.includes(hint)) return name;
    }
  }
  return null;
}

/**
 * Split CSV text into rows of cells (RFC 4180: double quotes, `""` escapes,
 * embedded newlines, CRLF or LF line endings) — the browser equivalent of
 * Python's `csv.reader` with the default dialect.
 */
export function parseCsvRows(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;
  let i = 0;

  const endField = () => {
    row.push(field);
    field = "";
  };
  const endRow = () => {
    endField();
    rows.push(row);
    row = [];
  };

  while (i < text.length) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          field += '"';
          i += 2;
          continue;
        }
        inQuotes = false;
        i += 1;
        continue;
      }
      field += ch;
      i += 1;
      continue;
    }
    if (ch === '"') {
      inQuotes = true;
      i += 1;
      continue;
    }
    if (ch === ",") {
      endField();
      i += 1;
      continue;
    }
    if (ch === "\r") {
      // Treat CRLF and a lone CR as one line terminator.
      endRow();
      i += text[i + 1] === "\n" ? 2 : 1;
      continue;
    }
    if (ch === "\n") {
      endRow();
      i += 1;
      continue;
    }
    field += ch;
    i += 1;
  }
  // A trailing newline produces no final row; anything else does.
  if (field !== "" || row.length > 0) endRow();
  return rows;
}

function decodeUtf8(content: Uint8Array): string {
  let text: string;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(content);
  } catch {
    throw new StatementParseError("file is not valid UTF-8 text");
  }
  // utf-8-sig: drop a leading byte-order mark.
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

/**
 * Parse CSV content into `ParsedRow`s plus a list of per-row parse errors.
 *
 * Throws `StatementParseError` if the file is empty/undecodable or lacks the
 * required date / description / amount columns. Individual rows that fail to
 * parse are collected as `RowError` (row number + reason), never aborting the
 * whole file.
 */
export function parseCsv(content: Uint8Array | string): ParseResult {
  const text =
    typeof content === "string" ? content : decodeUtf8(content);
  if (!text.trim()) throw new StatementParseError("file is empty");

  const table = parseCsvRows(text);
  const header = table.shift();
  if (!header || header.length === 0) {
    throw new StatementParseError("no CSV header row found");
  }

  const dateCol = matchColumn(header, DATE_HINTS);
  const descCol = matchColumn(header, DESC_HINTS);
  const amountCol = matchColumn(header, AMOUNT_HINTS);
  const debitCol = matchColumn(header, DEBIT_HINTS);
  const creditCol = matchColumn(header, CREDIT_HINTS);
  // Prefer a single signed amount column; otherwise fall back to a
  // debit/credit magnitude pair (spend = debit, income = credit).
  const hasAmount =
    amountCol !== null || debitCol !== null || creditCol !== null;
  const missing = [
    ["date", dateCol !== null] as const,
    ["description", descCol !== null] as const,
    ["amount", hasAmount] as const,
  ]
    .filter(([, present]) => !present)
    .map(([label]) => label);
  if (missing.length > 0) {
    throw new StatementParseError(
      "missing required column(s): " + missing.join(", "),
    );
  }

  // `csv.DictReader` keys cells by header name; duplicate headers collapse to
  // the last occurrence, and a short row leaves later keys unset.
  const indexOf = (name: string) => header.lastIndexOf(name);
  const dateIdx = indexOf(dateCol as string);
  const descIdx = indexOf(descCol as string);
  const amountIdx = amountCol === null ? -1 : indexOf(amountCol);
  const debitIdx = debitCol === null ? -1 : indexOf(debitCol);
  const creditIdx = creditCol === null ? -1 : indexOf(creditCol);
  const cell = (row: string[], idx: number) =>
    idx >= 0 && idx < row.length ? row[idx] : "";

  const rows: ParsedRow[] = [];
  const errors: RowError[] = [];
  // Data rows start at file line 2 (line 1 is the header).
  let lineNo = 1;
  for (const rawRow of table) {
    lineNo += 1;
    // DictReader skips genuinely blank lines.
    if (rawRow.length === 1 && rawRow[0] === "") {
      lineNo -= 1;
      continue;
    }
    let occurredOn: string;
    let signedAmount: number;
    try {
      occurredOn = parseDate(cell(rawRow, dateIdx));
      if (amountIdx >= 0) {
        signedAmount = parseAmount(cell(rawRow, amountIdx));
      } else {
        // Two-column debit/credit: spend is negative, income positive. Use
        // magnitudes so either column's sign representation works.
        const debitRaw = cell(rawRow, debitIdx);
        const creditRaw = cell(rawRow, creditIdx);
        if (!debitRaw.trim() && !creditRaw.trim()) {
          throw new RangeError("empty amount");
        }
        signedAmount =
          Math.abs(parseAmountOrZero(creditRaw)) -
          Math.abs(parseAmountOrZero(debitRaw));
      }
    } catch (exc) {
      if (exc instanceof RangeError) {
        errors.push({ row: lineNo, reason: exc.message });
        continue;
      }
      throw exc;
    }
    const merchant = cell(rawRow, descIdx).trim() || "Unknown";
    rows.push({ occurredOn, merchant, signedAmount });
  }
  return { rows, errors };
}

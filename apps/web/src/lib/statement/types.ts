/**
 * Shared shapes for the browser-side statement parser.
 *
 * This is a faithful TypeScript port of the Python ingest services
 * (`apps/api/app/services/statement_import.py`, `statement_pdf.py`) so a
 * statement can be parsed entirely on the user's device — the file never
 * leaves the browser.
 *
 * Amount convention: **negative = money out (spend), positive = money in
 * (income)**, matching the app-internal `Transaction.amount` sign.
 */

/** One successfully parsed transaction line. */
export interface ParsedRow {
  /** ISO calendar date, `YYYY-MM-DD`. */
  occurredOn: string;
  merchant: string;
  /** Negative = spend, positive = income. */
  signedAmount: number;
}

/**
 * A single data row that couldn't be parsed, with why.
 *
 * `row` is the 1-based line number in the uploaded file (the header is row 1,
 * so the first data row is row 2), so the user can locate the offending line
 * in their statement.
 */
export interface RowError {
  row: number;
  reason: string;
}

/** The result of parsing one statement file. */
export interface ParseResult {
  rows: ParsedRow[];
  errors: RowError[];
}

/**
 * Raised when a file cannot be parsed at all (bad header / empty / binary).
 *
 * Distinct from a per-row parse failure, which is collected as a `RowError`
 * and does not abort the parse.
 */
export class StatementParseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StatementParseError";
  }
}

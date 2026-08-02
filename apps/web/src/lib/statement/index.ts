/**
 * Browser-side statement parsing — the single entry point.
 *
 * Everything under `lib/statement` runs on the user's device: the uploaded
 * statement is read with the File API, parsed in-page, and never uploaded.
 */

import { parseCsv } from "./parse-csv";
import { parsePdf } from "./parse-pdf";
import { ParseResult, StatementParseError } from "./types";

export type { ParsedRow, ParseResult, RowError } from "./types";
export { StatementParseError } from "./types";
export { parseCsv, matchColumn, parseAmount, parseDate } from "./parse-csv";
export {
  parsePdf,
  rowsFromText,
  heuristicRows,
  inferYear,
  itemsToLines,
  NO_ROWS_REASON,
} from "./parse-pdf";
export { normalizeMerchant, extractProcessor } from "./merchant";
export { categorize, compileKeywords } from "./categorize";
export type { Category, CategoryResult } from "./categorize";

export interface ParseStatementOptions {
  /**
   * Credit-card account: its statement lists purchases as positive and
   * payments as negative, the opposite of our `negative = spend` convention,
   * so PDF amounts are sign-flipped. CSV exports already carry a signed
   * amount column, so this does not affect the CSV path.
   */
  isCredit: boolean;
}

function isPdf(file: File): boolean {
  return (
    file.type.toLowerCase() === "application/pdf" ||
    file.name.toLowerCase().endsWith(".pdf")
  );
}

/**
 * Parse an uploaded bank/credit-card statement into transactions.
 *
 * Dispatches on file type: PDFs go through `pdfjs-dist` text extraction plus
 * the date-led-line heuristic, everything else is treated as CSV.
 *
 * Throws `StatementParseError` for whole-file failures (empty, undecodable,
 * missing required columns, unreadable PDF). Rows that fail individually come
 * back in `errors` rather than aborting the parse.
 */
export async function parseStatement(
  file: File,
  opts: ParseStatementOptions,
): Promise<ParseResult> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (bytes.length === 0) throw new StatementParseError("file is empty");
  return isPdf(file) ? parsePdf(bytes, opts.isCredit) : parseCsv(bytes);
}

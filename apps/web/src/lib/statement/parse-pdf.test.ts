/** Mirrors `apps/api/tests/test_statement_pdf.py::TestHeuristicRows`. */
import { describe, expect, it } from "vitest";

import {
  NO_ROWS_REASON,
  heuristicRows,
  inferYear,
  itemsToLines,
  parsePdf,
  rowsFromText,
} from "./parse-pdf";
import { StatementParseError } from "./types";

const byMerchant = (rows: { merchant: string; signedAmount: number }[]) =>
  Object.fromEntries(rows.map((r) => [r.merchant, r.signedAmount]));

describe("heuristicRows", () => {
  it("parses date-led lines and takes the trailing amount", () => {
    const text =
      "DEMO STATEMENT\n" +
      "07/01/2026 ACME PAYROLL 3,200.00\n" +
      "07/03/2026 CHIPOTLE 452 -12.65\n" +
      "not a transaction line\n";
    const { rows, errors } = heuristicRows(text);
    const by = byMerchant(rows);
    expect(by["ACME PAYROLL"]).toBe(3200.0);
    // The LAST money token is the amount — "452" in the description must not
    // be mistaken for it.
    expect(by["CHIPOTLE 452"]).toBe(-12.65);
    expect(errors).toEqual([]);
  });

  it("treats a trailing minus as negative", () => {
    const { rows } = heuristicRows("07/04/2026 STORE 42.00-\n");
    expect(rows[0].signedAmount).toBe(-42.0);
  });

  it("reads accounting parentheses as negative", () => {
    const { rows } = heuristicRows("07/04/2026 STORE (42.00)\n");
    expect(rows[0].signedAmount).toBe(-42.0);
  });

  it("infers the statement year for bare MM/DD rows", () => {
    // Credit-card statements use MM/DD with no year; infer it from a full date
    // elsewhere in the text (e.g. the Opening/Closing line).
    const text =
      "Opening/Closing Date 06/05/26 - 07/04/26\n06/06 SQ *COFFEE BAR 8.56\n";
    const { rows } = heuristicRows(text);
    expect(rows[0].occurredOn).toBe("2026-06-06");
    expect(rows[0].signedAmount).toBe(8.56);
  });

  it("drops bare MM/DD rows when no year can be inferred", () => {
    const { rows } = heuristicRows("06/06 SQ *COFFEE BAR 8.56\n");
    expect(rows).toEqual([]);
  });

  it("flips the sign for credit accounts", () => {
    // Credit-card convention: purchase positive -> spend (negative);
    // payment negative -> credit (positive).
    const text =
      "Opening/Closing Date 06/05/26 - 07/04/26\n" +
      "06/06 SQ *COFFEE BAR 8.56\n" +
      "06/07 PAYMENT THANK YOU -100.00\n";
    const by = byMerchant(heuristicRows(text, true).rows);
    expect(by["SQ *COFFEE BAR"]).toBe(-8.56);
    expect(by["PAYMENT THANK YOU"]).toBe(100.0);
  });

  it("skips date-led lines with no money on them", () => {
    const { rows } = heuristicRows("07/01/2026 STATEMENT PERIOD SUMMARY\n");
    expect(rows).toEqual([]);
  });

  it("falls back to Unknown when the amount is the whole line", () => {
    const { rows } = heuristicRows("07/01/2026 12.00\n");
    expect(rows[0].merchant).toBe("Unknown");
  });
});

describe("inferYear", () => {
  it("normalizes 2-digit years from the first full date", () => {
    expect(inferYear("Opening/Closing Date 06/05/26 - 07/04/26")).toBe(2026);
    expect(inferYear("Statement 12/31/2025")).toBe(2025);
    expect(inferYear("no dates here")).toBeNull();
  });
});

describe("itemsToLines", () => {
  it("regroups positioned pdfjs runs into lines", () => {
    // pdfjs hands back independently-placed runs; the heuristic needs lines.
    const items = [
      { str: "07/01/2026", transform: [1, 0, 0, 1, 50, 700], width: 45 },
      { str: "ACME PAYROLL", transform: [1, 0, 0, 1, 120, 700], width: 60 },
      { str: "3,200.00", transform: [1, 0, 0, 1, 400, 700.4], width: 35 },
      { str: "07/03/2026", transform: [1, 0, 0, 1, 50, 680], width: 45 },
      { str: "CHIPOTLE 452", transform: [1, 0, 0, 1, 120, 680], width: 60 },
      { str: "-12.65", transform: [1, 0, 0, 1, 400, 680], width: 30 },
    ];
    const text = itemsToLines(items);
    expect(text).toBe(
      "07/01/2026 ACME PAYROLL 3,200.00\n07/03/2026 CHIPOTLE 452 -12.65",
    );
    // And that reconstruction feeds the heuristic end to end.
    const by = byMerchant(heuristicRows(text).rows);
    expect(by["ACME PAYROLL"]).toBe(3200.0);
    expect(by["CHIPOTLE 452"]).toBe(-12.65);
  });

  it("returns an empty string for a page with no text", () => {
    expect(itemsToLines([])).toBe("");
  });
});

describe("rowsFromText", () => {
  it("passes heuristic rows straight through", () => {
    const { rows, errors } = rowsFromText("07/03/2026 CHIPOTLE 452 -12.65\n");
    expect(rows).toHaveLength(1);
    expect(rows[0].signedAmount).toBe(-12.65);
    expect(errors).toEqual([]);
  });

  it("returns an explicit error instead of a silent empty result", () => {
    // There is no LLM fallback — the statement must never leave the device —
    // so "found nothing" has to be something the UI can show.
    const { rows, errors } = rowsFromText("a statement with no date-led lines");
    expect(rows).toEqual([]);
    expect(errors).toEqual([{ row: 0, reason: NO_ROWS_REASON }]);
  });

  it("flips signs for credit accounts through the same path", () => {
    const { rows } = rowsFromText("07/03/2026 CHIPOTLE 12.65\n", true);
    expect(rows[0].signedAmount).toBe(-12.65);
  });
});

describe("parsePdf", () => {
  it("rejects an empty file before touching pdfjs", async () => {
    // pdfjs itself is browser-only, so this guard is the part exercisable here.
    await expect(
      parsePdf(new TextEncoder().encode("   ")),
    ).rejects.toBeInstanceOf(StatementParseError);
  });
});

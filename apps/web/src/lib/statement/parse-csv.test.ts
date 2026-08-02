/** Mirrors `apps/api/tests/test_imports.py::TestParseUnit`. */
import { describe, expect, it } from "vitest";

import { matchColumn, parseAmount, parseCsv, parseDate } from "./parse-csv";
import { StatementParseError } from "./types";

const enc = (text: string) => new TextEncoder().encode(text);

describe("parseAmount", () => {
  it("handles currency symbols, separators and accounting parentheses", () => {
    expect(parseAmount("-5.75")).toBe(-5.75);
    expect(parseAmount("$1,234.56")).toBe(1234.56);
    expect(parseAmount("(50.00)")).toBe(-50.0);
    expect(parseAmount(" 12.00 ")).toBe(12.0);
    expect(parseAmount("($1,200.00)")).toBe(-1200.0);
  });

  it("throws on empty or non-numeric values", () => {
    for (const bad of ["", "   ", "abc", "1.2.3"]) {
      expect(() => parseAmount(bad)).toThrow(RangeError);
    }
  });
});

describe("parseDate", () => {
  it("accepts every supported format", () => {
    expect(parseDate("2026-06-01")).toBe("2026-06-01");
    expect(parseDate("06/01/2026")).toBe("2026-06-01");
    expect(parseDate("6/1/26")).toBe("2026-06-01");
    expect(parseDate("06-01-2026")).toBe("2026-06-01");
    expect(parseDate("2026/06/01")).toBe("2026-06-01");
    expect(parseDate("Jun 01, 2026")).toBe("2026-06-01");
    expect(parseDate("01 Jun 2026")).toBe("2026-06-01");
  });

  it("prefers MM/DD/YYYY over DD/MM/YYYY, matching the server", () => {
    expect(parseDate("07/08/2026")).toBe("2026-07-08");
    // Unambiguously day-first only once the first field can't be a month.
    expect(parseDate("13/05/2026")).toBe("2026-05-13");
  });

  it("expands 2-digit years the way Python does", () => {
    expect(parseDate("01/01/68")).toBe("2068-01-01");
    expect(parseDate("01/01/69")).toBe("1969-01-01");
  });

  it("rejects impossible and unrecognized dates", () => {
    for (const bad of ["", "not-a-date", "02/30/2026", "2026-13-01"]) {
      expect(() => parseDate(bad)).toThrow(RangeError);
    }
  });
});

describe("matchColumn", () => {
  it("honors hint priority over column order", () => {
    const header = ["Details", "Posting Date", "Description", "Amount"];
    expect(matchColumn(header, ["description", "details"])).toBe("Description");
  });

  it("returns null when nothing matches", () => {
    expect(matchColumn(["Foo", "Bar"], ["amount"])).toBeNull();
  });
});

describe("parseCsv", () => {
  it("parses header variants", () => {
    const { rows, errors } = parseCsv(
      enc("Transaction Date,Merchant,Amount\n06/01/2026,Coffee Shop,-3.50\n"),
    );
    expect(errors).toEqual([]);
    expect(rows).toEqual([
      { occurredOn: "2026-06-01", merchant: "Coffee Shop", signedAmount: -3.5 },
    ]);
  });

  it("skips bad rows with a line number and reason", () => {
    const { rows, errors } = parseCsv(
      enc(
        "Date,Description,Amount\n" +
          "2026-06-01,Good,-1.00\n" +
          "not-a-date,Bad Date,-2.00\n" +
          "2026-06-03,Bad Amount,notnum\n",
      ),
    );
    expect(rows).toHaveLength(1);
    expect(errors.map((e) => e.row)).toEqual([3, 4]);
    expect(errors[0].reason.toLowerCase()).toContain("date");
    expect(errors[1].reason).toBeTruthy();
  });

  it("raises when required columns are missing", () => {
    expect(() => parseCsv(enc("Foo,Bar\n1,2\n"))).toThrow(StatementParseError);
  });

  it("raises on an empty file", () => {
    expect(() => parseCsv(enc("   "))).toThrow(StatementParseError);
  });

  it("handles two-column debit/credit layouts", () => {
    // debit = spend (negative), credit = income (positive); a row populates
    // only one.
    const { rows, errors } = parseCsv(
      enc(
        "Date,Description,Debit,Credit\n" +
          "07/08/2026,Rent,1800.00,\n" +
          "07/09/2026,Refund,,45.00\n",
      ),
    );
    expect(errors).toEqual([]);
    const byMerchant = Object.fromEntries(
      rows.map((r) => [r.merchant, r.signedAmount]),
    );
    expect(byMerchant["Rent"]).toBe(-1800.0);
    expect(byMerchant["Refund"]).toBe(45.0);
  });

  it("uses magnitudes so a debit column exported as negative still spends", () => {
    const { rows } = parseCsv(
      enc("Date,Description,Debit,Credit\n07/08/2026,Rent,-1800.00,\n"),
    );
    expect(rows[0].signedAmount).toBe(-1800.0);
  });

  it("reports a debit/credit row with neither column filled", () => {
    const { rows, errors } = parseCsv(
      enc("Date,Description,Debit,Credit\n07/10/2026,Blank,,\n"),
    );
    expect(rows).toEqual([]);
    expect(errors).toHaveLength(1);
    expect(errors[0].reason).toContain("empty amount");
  });

  it("prefers a Description column over a leading Details column", () => {
    // A leading "Details" transaction-type column (DEBIT/CREDIT) must not be
    // picked as the merchant over the real "Description" column.
    const { rows, errors } = parseCsv(
      enc(
        "Details,Posting Date,Description,Amount,Type\n" +
          "DEBIT,07/01/2026,STARBUCKS STORE,-5.75,DEBIT_CARD\n",
      ),
    );
    expect(errors).toEqual([]);
    expect(rows[0].merchant).toBe("STARBUCKS STORE");
    expect(rows[0].signedAmount).toBe(-5.75);
  });

  it("prefers a single signed Amount column over a debit/credit pair", () => {
    const { rows } = parseCsv(
      enc("Date,Description,Amount,Debit,Credit\n07/01/2026,Thing,-9.99,,\n"),
    );
    expect(rows[0].signedAmount).toBe(-9.99);
  });

  it("falls back to Unknown for a blank description", () => {
    const { rows } = parseCsv(enc("Date,Description,Amount\n07/01/2026, ,-1.00\n"));
    expect(rows[0].merchant).toBe("Unknown");
  });

  it("handles quoted fields, embedded commas and a UTF-8 BOM", () => {
    const { rows, errors } = parseCsv(
      enc('﻿Date,Description,Amount\n07/01/2026,"ACME, INC.","-1,200.00"\n'),
    );
    expect(errors).toEqual([]);
    expect(rows[0].merchant).toBe("ACME, INC.");
    expect(rows[0].signedAmount).toBe(-1200.0);
  });

  it("ignores trailing blank lines", () => {
    const { rows, errors } = parseCsv(
      enc("Date,Description,Amount\n07/01/2026,Thing,-1.00\n\n"),
    );
    expect(rows).toHaveLength(1);
    expect(errors).toEqual([]);
  });
});

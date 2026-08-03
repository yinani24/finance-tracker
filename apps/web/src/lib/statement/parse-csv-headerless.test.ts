import { describe, expect, it } from "vitest";
import { parseCsv } from "./parse-csv";

/**
 * Chase's bank-account export is bare `date,description,amount` with no titles.
 * The parser used to reject it as having "no CSV header row found".
 */
const HEADERLESS = `2026-07-31,"NORTHWIND LABS PAYROLL",4800.00
2026-07-16,"NORTHWIND LABS PAYROLL",4800.00
2026-07-03,"CHASE CREDIT CRD EPAY",-1450.00
2026-07-02,"Interest Payment",46.56`;

describe("parseCsv — no header row", () => {
  it("infers columns from content and keeps every row", () => {
    const { rows, errors } = parseCsv(HEADERLESS);
    expect(errors).toEqual([]);
    expect(rows).toHaveLength(4);
    expect(rows[0]).toEqual({
      occurredOn: "2026-07-31",
      merchant: "NORTHWIND LABS PAYROLL",
      signedAmount: 4800.00,
    });
  });

  it("keeps income positive and spend negative", () => {
    const { rows } = parseCsv(HEADERLESS);
    expect(rows.filter((r) => r.signedAmount > 0)).toHaveLength(3);
    expect(rows.find((r) => r.merchant.includes("EPAY"))!.signedAmount).toBe(
      -1450.00,
    );
  });

  it("does not consume the first row as a header", () => {
    const { rows } = parseCsv(HEADERLESS);
    expect(rows.some((r) => r.occurredOn === "2026-07-31")).toBe(true);
  });

  it("still uses a real header when one is present", () => {
    const withHeader = `Date,Description,Amount\n2026-07-31,COFFEE,-4.50`;
    const { rows } = parseCsv(withHeader);
    expect(rows).toHaveLength(1);
    expect(rows[0].merchant).toBe("COFFEE");
  });

  it("handles columns in a different order", () => {
    const reordered = `"SOME SHOP",-12.34,2026-06-01\n"OTHER",-5.00,2026-06-02`;
    const { rows } = parseCsv(reordered);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toEqual({
      occurredOn: "2026-06-01",
      merchant: "SOME SHOP",
      signedAmount: -12.34,
    });
  });
});

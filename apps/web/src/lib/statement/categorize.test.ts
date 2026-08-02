/**
 * Mirrors `apps/api/tests/test_enrichment.py::TestRulesProvider` and
 * `::TestProcessorAndBoundaryRules`.
 */
import { describe, expect, it } from "vitest";

import { categorize } from "./categorize";

const cat = (merchant: string) => categorize(merchant).category;

describe("categorize — merchant keywords", () => {
  it("categorizes common merchants by name", () => {
    const cases: Record<string, string> = {
      "STARBUCKS #1122": "dining",
      "DOORDASH SUSHI": "dining",
      "WHOLE FOODS MKT": "groceries", // must NOT be dining
      "TRADER JOES": "groceries",
      "DELTA AIR LINES": "travel",
      "MARRIOTT HOTEL": "travel",
      "UBER TRIP": "transport",
      "AMAZON MKTPL": "shopping",
      "RENT PAYMENT": "bills",
      "PG&E ELECTRIC": "bills",
      "NETFLIX.COM": "entertainment",
      "CVS PHARMACY #4021": "health",
      "ACME CORP PAYROLL": "income",
    };
    for (const [merchant, expected] of Object.entries(cases)) {
      expect(cat(merchant), merchant).toBe(expected);
    }
  });

  it("falls back to other for an unknown merchant", () => {
    expect(cat("ZZZ QRSTUV LLC")).toBe("other");
    expect(cat("ZZZQQ HOLDINGS LLC")).toBe("other");
  });

  it("puts food delivery in dining, ahead of the bare uber transport rule", () => {
    expect(cat("UBER EATS")).toBe("dining");
    expect(cat("UBER TRIP HELP.UBER.COM")).toBe("transport");
  });

  it("reports confidence per precedence tier", () => {
    expect(categorize("STARBUCKS #1122").confidence).toBe(0.9);
    expect(categorize("TST* CHONG QING XIAO MIAN").confidence).toBe(0.7);
    expect(categorize("ZZZ QRSTUV LLC").confidence).toBe(0.3);
  });

  it("returns the normalized merchant alongside the category", () => {
    expect(categorize("DD *DOORDASH APPLEBEES 855-431-0459 CA")).toMatchObject({
      category: "dining",
      normalizedMerchant: "doordash applebees",
    });
    expect(categorize("").normalizedMerchant).toBeNull();
  });
});

describe("categorize — word boundaries and prefix keywords", () => {
  it("does not let 'mobil' match '...-Mobile'", () => {
    // "mobil" (the gas brand) must NOT match "Payment Thank You-Mobile",
    // which had been filing credit-card payments under transport.
    expect(cat("Payment Thank You-Mobile")).not.toBe("transport");
  });

  it("does not let 'food' match 'FOODS'", () => {
    // The dining rule has a bare "food"; without a closing boundary it would
    // steal "WHOLE FOODS" from groceries.
    expect(cat("WHOLE FOODS MKT")).toBe("groceries");
  });

  it("matches a prefix keyword run straight onto digits", () => {
    expect(cat("AMERICAN AIR0011111111111 FORT WORTH TX")).toBe("travel");
  });

  it("matches trader joe* against TRADER JOES", () => {
    expect(cat("TRADER JOES #182")).toBe("groceries");
    expect(cat("TRADER JOE'S")).toBe("groceries");
  });

  it("still matches keywords whose edge is not alphanumeric", () => {
    // No boundary is added next to a non-alphanumeric edge, so these survive.
    expect(cat("BOOKING.COM HOTEL RES")).toBe("travel");
    expect(cat("PG&E")).toBe("bills");
    expect(cat("DISNEY+ SUBSCRIPTION")).toBe("entertainment");
  });
});

describe("categorize — payment-processor fallback", () => {
  it("rescues an unknown merchant via its processor", () => {
    // We've never heard of these restaurants, but the processor tells us.
    expect(cat("TST* CHONG QING XIAO MIAN San Francisco CA")).toBe("dining");
    expect(cat("SQ *THE NOSH BOX San Francisco CA")).toBe("dining");
    expect(cat("IC* THE CORNER BODEGA")).toBe("groceries");
    expect(cat("BAYWHEE*2 RIDES HELP.LYFT.COM CA")).toBe("transport");
  });

  it("lets a known merchant keyword beat the processor", () => {
    // DD* is dining, but an explicit keyword still decides first.
    expect(cat("DD *DOORDASH APPLEBEES 855-431-0459 CA")).toBe("dining");
    // IC* is groceries, but Instacart-delivered restaurant is still the
    // keyword's call.
    expect(cat("IC* COSTCO BY INSTACART")).toBe("groceries");
  });

  it("falls through to other for an unrecognized processor", () => {
    expect(cat("ZZZZ*SOME PLACE")).toBe("other");
  });
});

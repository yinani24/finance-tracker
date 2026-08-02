/** Mirrors `apps/api/tests/test_merchant.py`. */
import { describe, expect, it } from "vitest";

import { extractProcessor, normalizeMerchant } from "./merchant";

describe("normalizeMerchant", () => {
  it("strips the Square prefix", () => {
    expect(
      normalizeMerchant("SQ *COFFEE BAR KEARNY San Francisco CA"),
    ).toMatch(/^COFFEE BAR/);
  });

  it("strips the Toast prefix", () => {
    expect(normalizeMerchant("TST* CHAAT DINER SF CA")).toMatch(/^CHAAT DINER/);
  });

  it("strips the DoorDash prefix, trailing phone and state", () => {
    expect(normalizeMerchant("DD *DOORDASH APPLEBEES 855-431-0459 CA")).toBe(
      "DOORDASH APPLEBEES",
    );
  });

  it("strips a trailing state and store number", () => {
    expect(normalizeMerchant("STARBUCKS STORE #1122 WA")).toBe(
      "STARBUCKS STORE",
    );
  });

  it("leaves a plain merchant unchanged", () => {
    expect(normalizeMerchant("WHOLE FOODS MARKET")).toBe("WHOLE FOODS MARKET");
  });

  it("collapses runs of whitespace", () => {
    expect(normalizeMerchant("  WHOLE   FOODS  ")).toBe("WHOLE FOODS");
  });

  it("handles empty input", () => {
    expect(normalizeMerchant("")).toBe("");
    expect(normalizeMerchant(null)).toBe("");
    expect(normalizeMerchant(undefined)).toBe("");
  });

  it("never empties the merchant entirely", () => {
    expect(normalizeMerchant("SQ *")).toBe("SQ *");
  });
});

describe("extractProcessor", () => {
  it("returns the upper-cased leading token", () => {
    expect(extractProcessor("TST* CHAAT DINER SF CA")).toBe("TST");
    expect(extractProcessor("SQ *THE NOSH BOX")).toBe("SQ");
    expect(extractProcessor("BAYWHEE*2 RIDES")).toBe("BAYWHEE");
    expect(extractProcessor("ic* costco by instacart")).toBe("IC");
  });

  it("returns null without a * marker", () => {
    expect(extractProcessor("WHOLE FOODS MARKET")).toBeNull();
    expect(extractProcessor("")).toBeNull();
    expect(extractProcessor(null)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";
import { normalizeMerchant, extractProcessor } from "./normalize-merchant";

/**
 * Every string here is taken verbatim from a real Chase statement. Before
 * normalization the top-merchant list was effectively a list of ticket
 * numbers: four American Airlines flights counted as four merchants.
 */
describe("normalizeMerchant", () => {
  it("collapses airline tickets to one airline", () => {
    const raw = [
      "AMERICAN AIR0011111111111 FORT WORTH TX",
      "AMERICAN AIR0011111111112 FORT WORTH TX",
      "AMERICAN AIR0011111111113 FORT WORTH TX",
      "AMERICAN AIR0011111111114 FORT WORTH TX",
    ];
    expect(raw.map(normalizeMerchant)).toEqual([
      "American Airlines",
      "American Airlines",
      "American Airlines",
      "American Airlines",
    ]);
  });

  it("strips a support URL and its trailing state", () => {
    expect(normalizeMerchant("UBER *TRIP HELP.UBER.COM CA")).toBe("Uber");
  });

  it("collapses Amazon order references", () => {
    expect(normalizeMerchant("AMAZON MKTPL*AB1CD2EF3 Amzn.com/bill WA")).toBe(
      "Amazon"
    );
    expect(normalizeMerchant("AMAZON MKTPL*GH4IJ5KL6 Amzn.com/bill WA")).toBe(
      "Amazon"
    );
  });

  it("handles Delta's space-separated ticket numbers", () => {
    expect(normalizeMerchant("DELTA AIR 0022222222221 SEATTLE WA")).toBe(
      "Delta Air Lines"
    );
    expect(normalizeMerchant("DELTA AIR 0022222222222 SEATTLE WA")).toBe(
      "Delta Air Lines"
    );
  });

  it("resolves an Instacart storefront to the store", () => {
    expect(
      normalizeMerchant("IC* COSTCO BY INSTACAR INSTACART.COM CA")
    ).toBe("Costco (Instacart)");
  });

  it("strips a processor prefix from an unknown merchant", () => {
    expect(normalizeMerchant("TST* CORNER BAKERY 415-555-0134 CA")).toBe(
      "Corner Bakery"
    );
    expect(normalizeMerchant("SQ *BLUE BOTTLE")).toBe("Blue Bottle");
  });

  it("keeps a merchant whose digits are part of the name", () => {
    expect(normalizeMerchant("7-ELEVEN 22 SEATTLE WA")).toBe("7-Eleven 22");
  });

  it("leaves already-readable mixed-case names alone", () => {
    expect(normalizeMerchant("Interest Payment")).toBe("Interest Payment");
  });

  it("never returns empty, even when everything looks like noise", () => {
    expect(normalizeMerchant("0011111111111 CA")).toBe("0011111111111 CA");
    expect(normalizeMerchant("999999")).toBe("999999");
    expect(normalizeMerchant("   ")).toBe("");
  });

  it("groups repeat charges from one merchant into a single key", () => {
    const uber = [
      "UBER *TRIP HELP.UBER.COM CA",
      "UBER   *TRIP HELP.UBER.COM CA",
      "UBER *TRIP 8005928996 CA",
    ].map(normalizeMerchant);
    expect(new Set(uber).size).toBe(1);
  });
});

describe("extractProcessor", () => {
  it("returns the stamped processor token", () => {
    expect(extractProcessor("DD *DOORDASH BOLLYWOOD")).toBe("DD");
    expect(extractProcessor("TST* CORNER BAKERY")).toBe("TST");
  });

  it("returns null when there is no marker", () => {
    expect(extractProcessor("AMERICAN AIR0011111111111")).toBeNull();
  });
});

describe("normalizeMerchant — brand collisions", () => {
  it("does not read American Express as an airline", () => {
    expect(normalizeMerchant("AMERICAN EXPRESS PAYMENT")).not.toContain(
      "Airlines"
    );
  });

  it("distinguishes Uber Eats from Uber rides", () => {
    expect(normalizeMerchant("UBER *EATS HELP.UBER.COM CA")).toBe("Uber Eats");
    expect(normalizeMerchant("UBER *TRIP HELP.UBER.COM CA")).toBe("Uber");
  });
});

describe("normalizeMerchant — Amazon descriptor shapes", () => {
  it("collapses every Amazon descriptor to one merchant", () => {
    const names = [
      "AMAZON MKTPL*AB1CD2EF3 Amzn.com/bill WA",
      "Amazon.com*MN7OP8QR9 Amzn.com/bill WA",
      "AMZN Mktp US*ST1UV2WX3",
      "AMAZON RETAIL* 7712 SEATTLE WA",
    ].map(normalizeMerchant);
    expect(new Set(names)).toEqual(new Set(["Amazon"]));
  });
});

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
      "AMERICAN AIR0017412354781 FORT WORTH TX",
      "AMERICAN AIR0017412354782 FORT WORTH TX",
      "AMERICAN AIR0017412225867 FORT WORTH TX",
      "AMERICAN AIR0017521226538 FORT WORTH TX",
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
    expect(normalizeMerchant("AMAZON MKTPL*T80A93XN3 Amzn.com/bill WA")).toBe(
      "Amazon"
    );
    expect(normalizeMerchant("AMAZON MKTPL*1U4CD8MR3 Amzn.com/bill WA")).toBe(
      "Amazon"
    );
  });

  it("handles Delta's space-separated ticket numbers", () => {
    expect(normalizeMerchant("DELTA AIR 0067493890566 SEATTLE WA")).toBe(
      "Delta Air Lines"
    );
    expect(normalizeMerchant("DELTA AIR 0067497239833 SEATTLE WA")).toBe(
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
    expect(normalizeMerchant("0017412354781 CA")).toBe("0017412354781 CA");
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
    expect(extractProcessor("AMERICAN AIR0017412354781")).toBeNull();
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
      "AMAZON MKTPL*T80A93XN3 Amzn.com/bill WA",
      "Amazon.com*KZ5738343 Amzn.com/bill WA",
      "AMZN Mktp US*2H4KL9QP1",
      "AMAZON RETAIL* 7712 SEATTLE WA",
    ].map(normalizeMerchant);
    expect(new Set(names)).toEqual(new Set(["Amazon"]));
  });
});

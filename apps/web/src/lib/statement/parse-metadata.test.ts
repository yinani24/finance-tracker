import { describe, expect, it } from "vitest";
import {
  parseStatementMetadata,
  statementLabel,
  statementUtilization,
} from "./parse-metadata";

// Verbatim excerpts from a real Chase Sapphire Preferred statement — the
// wording is what the extractor has to survive.
const CHASE = `
Manage your account online at: www.chase.com/cardhelp
ACCOUNT SUMMARY
Account Number: XXXX XXXX XXXX 1234
Previous Balance $2,848.21
Payment, Credits -$5,840.28
Purchases +$3,026.96
New Balance $34.89
Opening/Closing Date 06/05/26 - 07/04/26
Credit Access Line $9,100
Available Credit $9,065
Minimum Payment Due $34.89
With Sapphire Preferred, you'll earn 2x points on travel worldwide
`;

describe("parseStatementMetadata", () => {
  it("reads the card, issuer and account from a real Chase statement", () => {
    const m = parseStatementMetadata(CHASE);
    expect(m.issuer).toBe("Chase");
    expect(m.cardName).toBe("Sapphire Preferred");
    expect(m.last4).toBe("1234");
    expect(m.periodStart).toBe("06/05/26");
    expect(m.periodEnd).toBe("07/04/26");
  });

  it("reads limit and balance, so utilization needs no questions", () => {
    const m = parseStatementMetadata(CHASE);
    expect(m.creditLimit).toBe(9100);
    expect(m.currentBalance).toBe(34.89);
    expect(statementUtilization(m)).toBeCloseTo(34.89 / 9100, 5);
  });

  it("detects a credit-card statement, which sets the sign convention", () => {
    expect(parseStatementMetadata(CHASE).isCredit).toBe(true);
  });

  it("does not mistake a checking statement for a credit card", () => {
    const checking = `
      EVERYDAY CHECKING
      Beginning Balance $1,204.11
      Deposits and Additions $3,200.00
    `;
    expect(parseStatementMetadata(checking).isCredit).toBe(false);
  });

  it("prefers the longer product name", () => {
    expect(parseStatementMetadata("Chase Sapphire Reserve").cardName).toBe(
      "Sapphire Reserve"
    );
  });

  it("handles other issuers' wording for the limit", () => {
    const amex = "American Express Gold Card\nCredit Limit $12,500\nNew Balance $802.14";
    const m = parseStatementMetadata(amex);
    expect(m.issuer).toBe("American Express");
    expect(m.creditLimit).toBe(12500);
    expect(m.currentBalance).toBe(802.14);
  });

  it("returns undefined rather than guessing when a field is absent", () => {
    const m = parseStatementMetadata("Some unrelated document");
    expect(m.creditLimit).toBeUndefined();
    expect(m.cardName).toBeUndefined();
    expect(statementUtilization(m)).toBeNull();
  });

  it("labels the account from whatever was found", () => {
    expect(statementLabel(parseStatementMetadata(CHASE))).toBe(
      "Chase Sapphire Preferred ••1234"
    );
  });
});

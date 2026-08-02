import { describe, expect, it } from "vitest";
import {
  detectSubscriptions,
  categoryTotals,
  monthlyTrend,
  summarize,
} from "./derive";
import { EMPTY_SESSION, type SessionTransaction } from "./types";

let seq = 0;
function txn(
  merchant: string,
  occurredOn: string,
  amount: number,
  category = "bills"
): SessionTransaction {
  return { id: `t${seq++}`, merchant, occurredOn, amount, category };
}

describe("detectSubscriptions", () => {
  it("finds a monthly charge repeating at a stable price", () => {
    const subs = detectSubscriptions([
      txn("NETFLIX", "2026-04-03", -15.49, "entertainment"),
      txn("NETFLIX", "2026-05-03", -15.49, "entertainment"),
      txn("NETFLIX", "2026-06-03", -15.49, "entertainment"),
    ]);
    expect(subs).toHaveLength(1);
    expect(subs[0]).toMatchObject({
      merchant: "NETFLIX",
      period: "monthly",
      charges: 3,
      fixedAmount: true,
    });
    expect(subs[0].monthlyCost).toBeCloseTo(15.49, 2);
  });

  it("does not flag two coincidentally equal restaurant charges", () => {
    // The real false positive this rule exists for: one Chase statement had
    // two DoorDash orders a month apart for the same amount.
    const subs = detectSubscriptions([
      txn("DD *DOORDASH", "2026-06-05", -27.64, "dining"),
      txn("DD *DOORDASH", "2026-07-04", -27.64, "dining"),
    ]);
    expect(subs).toHaveLength(0);
  });

  it("accepts two charges when the amount is exact and the category bills", () => {
    const subs = detectSubscriptions([
      txn("ADOBE", "2026-06-01", -54.99),
      txn("ADOBE", "2026-07-01", -54.99),
    ]);
    expect(subs).toHaveLength(1);
    expect(subs[0].period).toBe("monthly");
  });

  it("rejects a merchant whose amounts vary", () => {
    const subs = detectSubscriptions([
      txn("CORNER CAFE", "2026-04-02", -4.5, "dining"),
      txn("CORNER CAFE", "2026-05-02", -12.0, "dining"),
      txn("CORNER CAFE", "2026-06-02", -8.25, "dining"),
    ]);
    expect(subs).toHaveLength(0);
  });

  it("normalizes a yearly charge to its monthly cost", () => {
    const subs = detectSubscriptions([
      txn("DOMAIN RENEWAL", "2024-06-01", -120),
      txn("DOMAIN RENEWAL", "2025-06-01", -120),
      txn("DOMAIN RENEWAL", "2026-06-01", -120),
    ]);
    expect(subs).toHaveLength(1);
    expect(subs[0].period).toBe("yearly");
    expect(subs[0].monthlyCost).toBeCloseTo(10, 2);
  });

  it("ignores income and single charges", () => {
    const subs = detectSubscriptions([
      txn("PAYROLL", "2026-06-01", 3000),
      txn("PAYROLL", "2026-07-01", 3000),
      txn("ONE OFF", "2026-06-10", -40),
    ]);
    expect(subs).toHaveLength(0);
  });
});

describe("categoryTotals", () => {
  it("totals spend per category and shares sum to one", () => {
    const cats = categoryTotals([
      txn("A", "2026-06-01", -75, "dining"),
      txn("B", "2026-06-02", -25, "travel"),
      txn("PAY", "2026-06-03", 500, "income"),
    ]);
    expect(cats[0]).toMatchObject({ category: "dining", total: 75, count: 1 });
    expect(cats.reduce((s, c) => s + c.share, 0)).toBeCloseTo(1, 6);
  });
});

describe("monthlyTrend", () => {
  it("splits spend and income by calendar month, oldest first", () => {
    const trend = monthlyTrend([
      txn("A", "2026-07-01", -10),
      txn("B", "2026-06-01", -20),
      txn("PAY", "2026-06-15", 100),
    ]);
    expect(trend.map((t) => t.month)).toEqual(["2026-06", "2026-07"]);
    expect(trend[0]).toMatchObject({ spend: 20, income: 100 });
  });
});

describe("detectSubscriptions — weak evidence", () => {
  it("does not call two charges eight days apart a weekly subscription", () => {
    // A real statement had one merchant charged twice at $5.98, eight days
    // apart. That is a habit, not a billing cycle.
    const subs = detectSubscriptions([
      txn("SPECIAL T", "2026-06-04", -5.98, "other"),
      txn("SPECIAL T", "2026-06-12", -5.98, "other"),
    ]);
    expect(subs).toHaveLength(0);
  });

  it("still accepts a genuine weekly charge once it repeats three times", () => {
    const subs = detectSubscriptions([
      txn("CLASSPASS", "2026-06-01", -19.0),
      txn("CLASSPASS", "2026-06-08", -19.0),
      txn("CLASSPASS", "2026-06-15", -19.0),
    ]);
    expect(subs).toHaveLength(1);
    expect(subs[0].period).toBe("weekly");
  });
});

describe("detectSubscriptions — food is never a subscription", () => {
  it("ignores DoorDash even at a perfect monthly cadence and price", () => {
    const subs = detectSubscriptions([
      txn("DD *DOORDASH BOLLYWOOD", "2026-05-04", -27.64, "dining"),
      txn("DD *DOORDASH BOLLYWOOD", "2026-06-04", -27.64, "dining"),
      txn("DD *DOORDASH BOLLYWOOD", "2026-07-04", -27.64, "dining"),
    ]);
    expect(subs).toHaveLength(0);
  });

  it("ignores a Toast terminal charged weekly for the same amount", () => {
    const subs = detectSubscriptions([
      txn("TST* CORNER CAFE", "2026-06-01", -12.5, "other"),
      txn("TST* CORNER CAFE", "2026-06-08", -12.5, "other"),
      txn("TST* CORNER CAFE", "2026-06-15", -12.5, "other"),
    ]);
    expect(subs).toHaveLength(0);
  });

  it("ignores a merchant whose name reads as food regardless of category", () => {
    const subs = detectSubscriptions([
      txn("BLUE BOTTLE COFFEE", "2026-05-02", -18.0, "other"),
      txn("BLUE BOTTLE COFFEE", "2026-06-02", -18.0, "other"),
      txn("BLUE BOTTLE COFFEE", "2026-07-02", -18.0, "other"),
    ]);
    expect(subs).toHaveLength(0);
  });

  it("still catches a real subscription that happens to be entertainment", () => {
    const subs = detectSubscriptions([
      txn("SPOTIFY USA", "2026-05-05", -11.99, "entertainment"),
      txn("SPOTIFY USA", "2026-06-05", -11.99, "entertainment"),
      txn("SPOTIFY USA", "2026-07-05", -11.99, "entertainment"),
    ]);
    expect(subs).toHaveLength(1);
    expect(subs[0].period).toBe("monthly");
  });
});

describe("transfers are neither income nor spend", () => {
  it("excludes credit-card payments from income", () => {
    // These come from a real Chase bank export loaded alongside the card
    // statement: counting them as income added $5,561 that was never earned.
    const cats = categoryTotals([
      txn("Payment Thank You-Mobile", "2026-07-03", 2992.07, "other"),
      txn("AUTOMATIC PAYMENT - THANK YOU", "2026-07-03", 869.52, "other"),
      txn("COFFEE", "2026-07-04", -5, "dining"),
    ]);
    expect(cats).toEqual([
      { category: "dining", total: 5, count: 1, share: 1 },
    ]);
  });

  it("excludes the paying side too, so spend is not double counted", () => {
    const trend = monthlyTrend([
      txn("CHASE CREDIT CRD EPAY", "2026-07-03", -2992.07, "other"),
      txn("BOTERO LABS PAYROLL", "2026-07-31", 4660.65, "income"),
    ]);
    expect(trend[0].spend).toBe(0);
    expect(trend[0].income).toBeCloseTo(4660.65, 2);
  });

  it("leaves ordinary merchants alone", () => {
    const trend = monthlyTrend([txn("PAYMENT PLAZA DINER", "2026-07-01", -20, "dining")]);
    expect(trend[0].spend).toBe(20);
  });
});

describe("averaging across files with different windows", () => {
  it("averages spend over months that contain spend, not every month loaded", () => {
    // A bank export back to January next to a card statement covering June and
    // July: dividing card spend across seven months understated it 3.5×, and
    // that average is what the card ranking engine reads.
    const s = summarize({
      ...EMPTY_SESSION,
      transactions: [
        txn("PAYROLL", "2026-01-31", 4000, "income"),
        txn("PAYROLL", "2026-02-28", 4000, "income"),
        txn("PAYROLL", "2026-03-31", 4000, "income"),
        txn("SHOP", "2026-06-10", -1000, "shopping"),
        txn("SHOP", "2026-07-10", -1000, "shopping"),
      ],
    });
    expect(s.months).toBe(5);
    expect(s.spendMonths).toBe(2);
    expect(s.incomeMonths).toBe(3);
    expect(s.monthlySpend).toBeCloseTo(1000, 2);
    expect(s.monthlyIncome).toBeCloseTo(4000, 2);
  });

  it("never divides by zero when one side is missing", () => {
    const s = summarize({
      ...EMPTY_SESSION,
      transactions: [txn("SHOP", "2026-06-10", -50, "shopping")],
    });
    expect(s.monthlyIncome).toBe(0);
    expect(s.monthlySpend).toBeCloseTo(50, 2);
  });
});

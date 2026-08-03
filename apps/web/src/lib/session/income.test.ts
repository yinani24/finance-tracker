import { describe, expect, it } from "vitest";
import { analyzeIncome, cadenceLabel } from "./income";
import type { SessionTransaction } from "./types";

let seq = 0;
function dep(merchant: string, occurredOn: string, amount: number): SessionTransaction {
  return { id: `i${seq++}`, merchant, occurredOn, amount, category: "income" };
}

/** The payroll rows from a real Chase bank export, verbatim. */
const PAYROLL = [
  dep("NORTHWIND LABS PAYROLL", "2026-05-29", 5100.00),
  dep("NORTHWIND LABS PAYROLL", "2026-06-15", 5100.00),
  dep("NORTHWIND LABS PAYROLL", "2026-06-30", 5100.00),
  dep("NORTHWIND LABS PAYROLL", "2026-07-16", 4800.00),
  dep("NORTHWIND LABS PAYROLL", "2026-07-31", 4800.00),
];

const INTEREST = [
  dep("Interest Payment", "2026-01-02", 28.35),
  dep("Interest Payment", "2026-02-02", 27.71),
  dep("Interest Payment", "2026-03-02", 25.1),
  dep("Interest Payment", "2026-04-02", 27.43),
  dep("Interest Payment", "2026-05-02", 26.23),
  dep("Interest Payment", "2026-06-02", 28.82),
  dep("Interest Payment", "2026-07-02", 46.56),
];

describe("analyzeIncome", () => {
  it("reads a semi-monthly salary as 24 pay periods, not 26", () => {
    const { primary } = analyzeIncome(PAYROLL);
    expect(primary?.merchant).toBe("NORTHWIND LABS PAYROLL");
    expect(primary?.cadence).toBe("semimonthly");
    // Median of the three most recent deposits, so a pay change wins over history.
    expect(primary?.amount).toBeCloseTo(4800.00, 2);
    expect(primary?.annualized).toBeCloseTo(4800.00 * 24, 2);
  });

  it("does not dilute salary across months that predate the job", () => {
    // Seven months of file, salary starting in month five. Averaging total
    // income over the file reports about a third of the real figure.
    const { monthlyRecurring } = analyzeIncome([...PAYROLL, ...INTEREST]);
    expect(monthlyRecurring).toBeGreaterThan(9_000);
    const naive =
      [...PAYROLL, ...INTEREST].reduce((s, t) => s + t.amount, 0) / 7;
    expect(naive).toBeLessThan(3_600);
  });

  it("recognises monthly interest as recurring but keeps it separate", () => {
    const { sources, primary } = analyzeIncome([...PAYROLL, ...INTEREST]);
    const interest = sources.find((s) => s.merchant === "Interest Payment")!;
    expect(interest.cadence).toBe("monthly");
    expect(interest.isRecurring).toBe(true);
    expect(interest.looksLikePayroll).toBe(false);
    // Primary is the largest recurring source, so interest never leads.
    expect(primary?.merchant).toBe("NORTHWIND LABS PAYROLL");
  });

  it("flags a payroll name", () => {
    expect(analyzeIncome(PAYROLL).primary?.looksLikePayroll).toBe(true);
  });

  it("treats a lone deposit as irregular and does not project it", () => {
    const { sources, monthlyRecurring } = analyzeIncome([
      dep("TAX REFUND", "2026-04-15", 3200),
    ]);
    expect(sources[0].isRecurring).toBe(false);
    expect(sources[0].cadence).toBe("irregular");
    expect(monthlyRecurring).toBe(0);
  });

  it("does not call two deposits a fortnight apart a salary", () => {
    const { sources } = analyzeIncome([
      dep("SOME CLIENT", "2026-06-01", 500),
      dep("SOME CLIENT", "2026-06-15", 500),
    ]);
    expect(sources[0].isRecurring).toBe(false);
  });

  it("separates fortnightly pay from twice-monthly pay", () => {
    const fortnightly = [
      "2026-05-01", "2026-05-15", "2026-05-29",
      "2026-06-12", "2026-06-26", "2026-07-10", "2026-07-24",
    ].map((d) => dep("ACME PAYROLL", d, 3000));
    expect(analyzeIncome(fortnightly).primary?.cadence).toBe("biweekly");
    expect(analyzeIncome(fortnightly).primary?.annualized).toBeCloseTo(3000 * 26, 2);
  });

  it("ignores spending entirely", () => {
    const { sources } = analyzeIncome([
      dep("SHOP", "2026-06-01", -50),
      ...PAYROLL,
    ]);
    expect(sources.map((s) => s.merchant)).not.toContain("SHOP");
  });

  it("excludes card payments, which are transfers rather than earnings", () => {
    const { sources } = analyzeIncome([
      dep("Payment Thank You-Mobile", "2026-07-03", 1450.00),
      ...PAYROLL,
    ]);
    expect(sources.map((s) => s.merchant)).not.toContain(
      "Payment Thank You-Mobile"
    );
  });
});

describe("cadenceLabel", () => {
  it("reads as English", () => {
    expect(cadenceLabel("semimonthly")).toBe("twice a month");
    expect(cadenceLabel("biweekly")).toBe("every two weeks");
  });
});

import { describe, expect, it } from "vitest";
import { buildNarrative } from "./narrative";
import { EMPTY_SESSION, type SessionState, type SessionTransaction } from "./types";

let seq = 0;
const t = (
  merchant: string,
  occurredOn: string,
  amount: number,
  category = "dining"
): SessionTransaction => ({
  id: `n${seq++}`, merchant, occurredOn, amount, category,
});

const session = (p: Partial<SessionState>): SessionState => ({ ...EMPTY_SESSION, ...p });

describe("buildNarrative", () => {
  it("says nothing is loaded rather than inventing a summary", () => {
    const n = buildNarrative(EMPTY_SESSION);
    expect(n.headline).toMatch(/nothing loaded/i);
    expect(n.points).toEqual([]);
  });

  it("leads with the monthly figure and the dominant category", () => {
    const n = buildNarrative(
      session({
        transactions: [
          t("A", "2026-06-01", -700, "travel"),
          t("B", "2026-06-02", -300, "dining"),
        ],
      })
    );
    expect(n.headline).toContain("travel");
    expect(n.headline).toMatch(/70%/);
  });

  it("distinguishes concentrated spending from spread-out spending", () => {
    const concentrated = buildNarrative(
      session({
        transactions: [
          t("A", "2026-06-01", -600, "travel"),
          t("B", "2026-06-02", -300, "dining"),
          t("C", "2026-06-03", -100, "shopping"),
        ],
      })
    );
    expect(concentrated.points.join(" ")).toMatch(/concentrated enough/);

    const spread = buildNarrative(
      session({
        transactions: [
          t("A", "2026-06-01", -100, "travel"),
          t("B", "2026-06-02", -100, "dining"),
          t("C", "2026-06-03", -100, "shopping"),
          t("D", "2026-06-04", -100, "groceries"),
          t("E", "2026-06-05", -100, "health"),
        ],
      })
    );
    expect(spread.points.join(" ")).toMatch(/spread fairly evenly|flat-rate/);
  });

  it("asks for more statements when only one month is loaded", () => {
    const n = buildNarrative(
      session({ transactions: [t("A", "2026-06-01", -50)] })
    );
    expect(n.suggestion).toMatch(/another month/i);
  });

  it("flags spending above income rather than burying it", () => {
    const n = buildNarrative(
      session({
        transactions: [
          t("RENT", "2026-06-01", -3000, "bills"),
          t("RENT", "2026-07-01", -3000, "bills"),
          t("PAY", "2026-06-02", 1000, "income"),
          t("PAY", "2026-06-16", 1000, "income"),
          t("PAY", "2026-06-30", 1000, "income"),
          t("PAY", "2026-07-15", 1000, "income"),
        ],
      })
    );
    expect(n.points.join(" ")).toMatch(/more than you bring in/);
  });

  it("never spells a number as a digit mid-sentence for small counts", () => {
    const n = buildNarrative(
      session({
        transactions: [
          t("NETFLIX", "2026-05-03", -15.49, "entertainment"),
          t("NETFLIX", "2026-06-03", -15.49, "entertainment"),
          t("NETFLIX", "2026-07-03", -15.49, "entertainment"),
        ],
      })
    );
    const subLine = n.points.find((p) => /recurring/.test(p));
    expect(subLine).toMatch(/^one recurring charge costs/);
  });
});

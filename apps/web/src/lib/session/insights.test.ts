import { describe, expect, it } from "vitest";
import { buildInsights, type CategoryAssignment } from "./insights";
import { EMPTY_SESSION, type SessionState, type SessionTransaction } from "./types";

let seq = 0;
function txn(
  merchant: string,
  occurredOn: string,
  amount: number,
  category = "bills",
  sourceId?: string
): SessionTransaction {
  return { id: `t${seq++}`, merchant, occurredOn, amount, category, sourceId };
}

function session(partial: Partial<SessionState>): SessionState {
  return { ...EMPTY_SESSION, ...partial };
}

describe("buildInsights", () => {
  it("says nothing when there is nothing to say", () => {
    expect(buildInsights(EMPTY_SESSION)).toEqual([]);
  });

  it("totals subscriptions and states the annual commitment", () => {
    const insights = buildInsights(
      session({
        transactions: [
          txn("NETFLIX", "2026-04-03", -15.49, "entertainment"),
          txn("NETFLIX", "2026-05-03", -15.49, "entertainment"),
          txn("NETFLIX", "2026-06-03", -15.49, "entertainment"),
        ],
      })
    );
    const total = insights.find((i) => i.id === "subscriptions-total");
    expect(total).toBeDefined();
    expect(total!.impactAnnual).toBeCloseTo(15.49 * 12, 2);
  });

  it("flags utilization over 30% and says what to pay down", () => {
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "c1", name: "Card", creditLimit: 10_000, currentBalance: 4_500 },
        ],
      })
    );
    const util = insights.find((i) => i.id === "utilization");
    expect(util).toBeDefined();
    expect(util!.severity).toBe("warning");
    // 4500 - (10000 * 0.3) = 1500
    expect(util!.evidence.some((e) => e.value.includes("1,500"))).toBe(true);
  });

  it("escalates utilization above 50% to critical", () => {
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "c1", name: "Card", creditLimit: 1_000, currentBalance: 700 },
        ],
      })
    );
    expect(insights.find((i) => i.id === "utilization")!.severity).toBe("critical");
  });

  it("stays quiet about utilization under 30%", () => {
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "c1", name: "Card", creditLimit: 10_000, currentBalance: 500 },
        ],
      })
    );
    expect(insights.find((i) => i.id === "utilization")).toBeUndefined();
  });

  it("reports negative cashflow only when income is known", () => {
    const spendOnly = session({
      transactions: [txn("RENT", "2026-06-01", -2000)],
    });
    expect(buildInsights(spendOnly).find((i) => i.id === "cashflow-negative")).toBeUndefined();

    const withIncome = session({
      transactions: [
        txn("RENT", "2026-06-01", -2000),
        txn("PAYROLL", "2026-06-02", 1500),
      ],
    });
    const cf = buildInsights(withIncome).find((i) => i.id === "cashflow-negative");
    expect(cf).toBeDefined();
    expect(cf!.impactAnnual).toBeCloseTo(-500 * 12, 2);
  });

  it("prices moving a category onto the better card held", () => {
    const assignments: CategoryAssignment[] = [
      {
        category: "travel",
        best_card: { name: "Sapphire Preferred", issuer: "CHASE" },
        rate: 2,
        card_rates: { "Sapphire Preferred": 2, "Freedom Unlimited": 1.5 },
      },
    ];
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "a", name: "Sapphire Preferred" },
          { id: "b", name: "Freedom Unlimited" },
        ],
        // $1,000 of travel in one month, on the weaker card.
        transactions: [txn("AIRLINE", "2026-06-01", -1000, "travel", "b")],
      }),
      assignments
    );
    const wrong = insights.find((i) => i.id.startsWith("wrong-card-travel"));
    expect(wrong).toBeDefined();
    // $12,000/yr * (2% - 1.5%) = $60
    expect(wrong!.impactAnnual).toBeCloseTo(60, 2);
  });

  it("does not flag a category already on the best card", () => {
    const assignments: CategoryAssignment[] = [
      {
        category: "travel",
        best_card: { name: "Sapphire Preferred", issuer: "CHASE" },
        rate: 2,
        card_rates: { "Sapphire Preferred": 2, "Freedom Unlimited": 1.5 },
      },
    ];
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "a", name: "Sapphire Preferred" },
          { id: "b", name: "Freedom Unlimited" },
        ],
        transactions: [txn("AIRLINE", "2026-06-01", -1000, "travel", "a")],
      }),
      assignments
    );
    expect(
      insights.find((i) => i.id.startsWith("wrong-card-travel"))
    ).toBeUndefined();
  });

  it("ranks by annual impact, keeping critical findings on top", () => {
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "c1", name: "Card", creditLimit: 1_000, currentBalance: 900 },
        ],
        transactions: [
          txn("RENT", "2026-06-01", -3000),
          txn("PAYROLL", "2026-06-02", 1000),
        ],
      })
    );
    // Utilization has no dollar figure but is critical, so it must not sink
    // below the ranked-by-impact items.
    expect(insights[0].severity).toBe("critical");
  });
});

describe("buildInsights — lookup failures", () => {
  it("stays quiet when every rate is zero, which means the card never matched", () => {
    // A statement-derived name like "Chase Sapphire Preferred ••3146" does not
    // match the dataset key, so every rate returns 0. Reporting "earns only 0%"
    // off that is a false claim about a card that earns 2% on travel.
    const insights = buildInsights(
      session({
        heldCards: [{ id: "a", name: "Chase Sapphire Preferred ••3146" }],
        transactions: [txn("AIRLINE", "2026-06-01", -1000, "travel", "a")],
      }),
      [
        {
          category: "travel",
          best_card: { name: "Chase Sapphire Preferred ••3146", issuer: "CHASE" },
          rate: 0,
          card_rates: { "Chase Sapphire Preferred ••3146": 0 },
        },
      ]
    );
    expect(insights.find((i) => i.id.startsWith("unrewarded"))).toBeUndefined();
  });

  it("gives each wrong-card finding a distinct id per card", () => {
    const insights = buildInsights(
      session({
        heldCards: [
          { id: "a", name: "Best" },
          { id: "b", name: "Weak One" },
          { id: "c", name: "Weak Two" },
        ],
        transactions: [
          txn("X", "2026-06-01", -1000, "travel", "b"),
          txn("Y", "2026-06-02", -1000, "travel", "c"),
        ],
      }),
      [
        {
          category: "travel",
          best_card: { name: "Best", issuer: "CHASE" },
          rate: 3,
          card_rates: { Best: 3, "Weak One": 1, "Weak Two": 1 },
        },
      ]
    );
    const ids = insights.filter((i) => i.id.startsWith("wrong-card")).map((i) => i.id);
    expect(ids).toHaveLength(2);
    expect(new Set(ids).size).toBe(2);
  });
});

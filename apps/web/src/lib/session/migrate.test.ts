import { describe, expect, it } from "vitest";
import { migrate } from "./migrate";
import { EMPTY_SESSION, type SessionTransaction } from "./types";

function txn(merchant: string, extra: Partial<SessionTransaction> = {}) {
  return {
    id: "t1",
    occurredOn: "2026-07-01",
    merchant,
    amount: -10,
    category: "travel",
    ...extra,
  } as SessionTransaction;
}

describe("migrate", () => {
  it("normalizes merchants stored before normalization existed", () => {
    const out = migrate({
      ...EMPTY_SESSION,
      transactions: [txn("AMERICAN AIR0011111111111 FORT WORTH TX")],
    });
    expect(out.transactions[0].merchant).toBe("American Airlines");
  });

  it("keeps the original descriptor so nothing is lost", () => {
    const raw = "UBER *TRIP HELP.UBER.COM CA";
    const out = migrate({ ...EMPTY_SESSION, transactions: [txn(raw)] });
    expect(out.transactions[0].rawMerchant).toBe(raw);
  });

  it("is idempotent — a second pass changes nothing", () => {
    const once = migrate({
      ...EMPTY_SESSION,
      transactions: [txn("AMAZON MKTPL*AB1CD2EF3 Amzn.com/bill WA")],
    });
    expect(migrate(once)).toEqual(once);
  });

  it("leaves an already-migrated transaction untouched", () => {
    const session = {
      ...EMPTY_SESSION,
      transactions: [
        txn("Some Hand Edited Name", { rawMerchant: "SQ *SOMETHING ELSE" }),
      ],
    };
    expect(migrate(session).transactions[0].merchant).toBe(
      "Some Hand Edited Name"
    );
  });

  it("returns the same object when there is nothing to do", () => {
    expect(migrate(EMPTY_SESSION)).toBe(EMPTY_SESSION);
  });
});

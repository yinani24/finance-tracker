"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Trash2, ArrowRight, ShieldCheck } from "lucide-react";
import { useSession } from "@/lib/session/session-context";
import { utilization, type ScoreBand } from "@/lib/session/types";
import { formatCurrency } from "@/lib/format";

/**
 * Onboarding questionnaire.
 *
 * Two questions, then the upload. We only ask for things that measurably
 * change the output: the credit band and application count drive approval
 * odds, and each card's limit + balance give us utilization — roughly 30% of a
 * FICO score and the strongest signal obtainable without a credit bureau.
 * There is no public API that will hand a consumer their own limit or balance
 * without FCRA-gated access, so asking is the honest route.
 */

const BANDS: { value: ScoreBand; label: string }[] = [
  { value: "excellent", label: "Excellent — 740+" },
  { value: "good", label: "Good — 670–739" },
  { value: "fair", label: "Fair — 580–669" },
  { value: "poor", label: "Poor — below 580" },
];

export default function StartPage() {
  const router = useRouter();
  const { session, setCredit, addCard, removeCard, setStep } = useSession();
  const [stage, setStage] = useState<"credit" | "cards">("credit");

  const [name, setName] = useState("");
  const [limit, setLimit] = useState("");
  const [balance, setBalance] = useState("");

  const util = utilization(session.heldCards);

  function submitCard(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    addCard({
      name: name.trim(),
      creditLimit: limit ? Number(limit) : undefined,
      currentBalance: balance ? Number(balance) : undefined,
    });
    setName("");
    setLimit("");
    setBalance("");
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-card-foreground">Set up your session</h1>
        <p className="text-sm text-muted mt-1">
          Two quick questions, then add your statements.
        </p>
      </div>

      {/* Privacy is the product here, so state it plainly and early. */}
      <div className="mb-8 flex items-start gap-3 border border-border p-4">
        <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" />
        <p className="text-sm text-muted">
          Everything you enter stays in this browser tab and is erased when you
          close it. Nothing is uploaded to a server or saved to a database.
        </p>
      </div>

      {stage === "credit" ? (
        <section>
          <h2 className="text-card-foreground">Your credit standing</h2>
          <p className="mt-1 mb-5 text-sm text-muted">
            Optional. Used to estimate approval odds, so we stop recommending
            cards you are unlikely to get.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted">
                Credit score range
              </span>
              <select
                value={session.credit.scoreBand ?? ""}
                onChange={(e) =>
                  setCredit({ scoreBand: (e.target.value || undefined) as ScoreBand })
                }
                className="w-full border border-input bg-background px-3 py-2 text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
              >
                <option value="">Prefer not to say</option>
                {BANDS.map((b) => (
                  <option key={b.value} value={b.value}>
                    {b.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted">
                Cards opened in the last 24 months
              </span>
              <input
                type="number"
                min={0}
                max={20}
                placeholder="e.g. 2"
                value={session.credit.recentApplications ?? ""}
                onChange={(e) =>
                  setCredit({
                    recentApplications: e.target.value ? Number(e.target.value) : undefined,
                  })
                }
                className="w-full border border-input bg-background px-3 py-2 font-mono text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
              <span className="mt-1 block text-xs text-muted-foreground">
                Some issuers decline past a threshold — Chase at 5.
              </span>
            </label>
          </div>

          <button
            onClick={() => setStage("cards")}
            className="mt-6 inline-flex items-center gap-2 bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground motion-base hover:bg-primary-hover"
          >
            Continue <ArrowRight className="h-4 w-4" />
          </button>
        </section>
      ) : (
        <section>
          <h2 className="text-card-foreground">Cards you already have</h2>
          <p className="mt-1 mb-5 text-sm text-muted">
            The limit and balance give us your utilization — about 30% of a
            credit score, and the biggest thing we can work out without pulling
            a credit report.
          </p>

          {session.heldCards.length > 0 && (
            <div className="mb-5 border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Card</th>
                    <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Limit</th>
                    <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Balance</th>
                    <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Used</th>
                    <th className="w-10" />
                  </tr>
                </thead>
                <tbody>
                  {session.heldCards.map((c) => {
                    const used =
                      c.creditLimit && c.creditLimit > 0
                        ? (c.currentBalance ?? 0) / c.creditLimit
                        : null;
                    return (
                      <tr key={c.id} className="border-b border-border last:border-0">
                        <td className="px-3 py-2 text-card-foreground">{c.name}</td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">
                          {c.creditLimit ? formatCurrency(c.creditLimit) : "—"}
                        </td>
                        <td className="px-3 py-2 text-right font-mono tabular-nums">
                          {c.currentBalance != null ? formatCurrency(c.currentBalance) : "—"}
                        </td>
                        <td
                          className={
                            "px-3 py-2 text-right font-mono tabular-nums " +
                            (used != null && used > 0.3 ? "text-destructive" : "text-muted")
                          }
                        >
                          {used != null ? `${Math.round(used * 100)}%` : "—"}
                        </td>
                        <td className="px-3 py-2 text-right">
                          <button
                            onClick={() => removeCard(c.id)}
                            aria-label={`Remove ${c.name}`}
                            className="text-muted-foreground motion-base hover:text-destructive"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {util != null && (
            <p className="mb-5 text-sm text-muted">
              Overall utilization:{" "}
              <span
                className={
                  "font-mono tabular-nums " +
                  (util > 0.3 ? "text-destructive" : "text-success")
                }
              >
                {Math.round(util * 100)}%
              </span>
              {util > 0.3 && " — above 30% typically weighs on a score."}
            </p>
          )}

          <form onSubmit={submitCard} className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto]">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Card name, e.g. Chase Sapphire"
              className="border border-input bg-background px-3 py-2 text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            <input
              type="number"
              value={limit}
              onChange={(e) => setLimit(e.target.value)}
              placeholder="Limit"
              className="w-32 border border-input bg-background px-3 py-2 font-mono text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            <input
              type="number"
              value={balance}
              onChange={(e) => setBalance(e.target.value)}
              placeholder="Balance"
              className="w-32 border border-input bg-background px-3 py-2 font-mono text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 border border-border px-3 py-2 text-sm text-card-foreground motion-base hover:bg-accent"
            >
              <Plus className="h-4 w-4" /> Add
            </button>
          </form>

          <div className="mt-8 flex items-center gap-3">
            <button
              onClick={() => {
                setStep("upload");
                router.push("/transactions");
              }}
              className="inline-flex items-center gap-2 bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground motion-base hover:bg-primary-hover"
            >
              Add statements <ArrowRight className="h-4 w-4" />
            </button>
            <button
              onClick={() => setStage("credit")}
              className="text-sm text-muted motion-base hover:text-card-foreground"
            >
              Back
            </button>
          </div>
        </section>
      )}
    </div>
  );
}

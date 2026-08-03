"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2, X } from "lucide-react";
import { postStatelessPortfolio, hasApi } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { useSession } from "@/lib/session/session-context";
import { summarize, categoryTotals } from "@/lib/session/derive";
import { StatementDropzone } from "@/components/statement-dropzone";

/**
 * The cards you hold, and whether they fit how you actually spend.
 *
 * Cards arrive two ways: read out of an uploaded statement, or added by hand
 * here for a card whose statement hasn't been uploaded. Both live in the
 * session — adding one used to POST to the server, which silently failed
 * because the client-only flow never creates the account that write needs.
 */
export default function PortfolioPage() {
  const { session, ready, addCard, updateCard, removeCard } = useSession();
  const [adding, setAdding] = useState(false);
  const [draft, setDraft] = useState({
    name: "",
    issuer: "",
    creditLimit: "",
    currentBalance: "",
  });

  const summary = useMemo(() => summarize(session), [session]);
  const cats = useMemo(
    () => categoryTotals(session.transactions),
    [session.transactions]
  );

  const { data } = useQuery({
    queryKey: [
      "portfolio",
      "stateless",
      session.heldCards.map((c) => c.name).join(","),
      Math.round(summary.monthlySpend),
    ],
    enabled: ready && hasApi && session.heldCards.length > 0,
    queryFn: () =>
      postStatelessPortfolio({
        avg_monthly_spend: summary.monthlySpend,
        category_breakdown: Object.fromEntries(
          cats.map((c) => [c.category, c.total / summary.months])
        ),
        held_cards: session.heldCards.map((c) => ({
          // The dataset is keyed on the product name, not the display label.
          name: c.productName ?? c.name,
          issuer: c.issuer,
        })),
      }),
  });

  function submit() {
    const name = draft.name.trim();
    if (!name) return;
    addCard({
      name,
      issuer: draft.issuer.trim() || undefined,
      creditLimit: draft.creditLimit ? Number(draft.creditLimit) : undefined,
      currentBalance: draft.currentBalance
        ? Number(draft.currentBalance)
        : undefined,
    });
    setDraft({ name: "", issuer: "", creditLimit: "", currentBalance: "" });
    setAdding(false);
  }

  const best = data?.best_per_category ?? [];
  const bestAvailable = data?.best_available_per_category ?? [];

  // What each category is worth per year, so a rate gap can be shown in
  // dollars rather than percentage points.
  const annualByCategory = new Map(
    cats.map((c) => [c.category, (c.total / summary.months) * 12])
  );

  const gaps = bestAvailable
    .map((b) => {
      const held = best.find((x) => x.category === b.category);
      const heldRate = held?.rate ?? 0;
      const annual = annualByCategory.get(b.category) ?? 0;
      const gain = (annual * (b.rate - heldRate)) / 100;
      return { ...b, heldRate, heldCard: held?.best_card?.name ?? null, annual, gain };
    })
    .filter((g) => g.gain > 0)
    .sort((a, b) => b.gain - a.gain);

  const totalGain = gaps.reduce((s, g) => s + g.gain, 0);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">Portfolio</h1>
          <p className="text-sm text-muted mt-1">
            {session.heldCards.length} card
            {session.heldCards.length === 1 ? "" : "s"}
            {summary.creditLimit
              ? ` · ${formatCurrency(summary.currentBalance ?? 0)} of ${formatCurrency(summary.creditLimit)} used`
              : ""}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setAdding((v) => !v)}
          className="motion-base flex flex-shrink-0 items-center gap-2 border border-border px-3 py-2 text-sm hover:bg-accent/40"
        >
          {adding ? (
            <>
              <X className="h-4 w-4" /> Cancel
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" /> Add a card
            </>
          )}
        </button>
      </div>

      {adding && (
        <div className="border border-border p-6 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="text-sm">
              <span className="text-muted">Card name</span>
              <input
                autoFocus
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="Sapphire Preferred"
                className="mt-1 w-full border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40 motion-base"
              />
            </label>
            <label className="text-sm">
              <span className="text-muted">Issuer</span>
              <input
                value={draft.issuer}
                onChange={(e) => setDraft({ ...draft, issuer: e.target.value })}
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="Chase"
                className="mt-1 w-full border border-input bg-background px-3 py-2 text-sm text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40 motion-base"
              />
            </label>
            <label className="text-sm">
              <span className="text-muted">Credit limit</span>
              <input
                inputMode="decimal"
                value={draft.creditLimit}
                onChange={(e) =>
                  setDraft({ ...draft, creditLimit: e.target.value })
                }
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="9100"
                className="mt-1 w-full border border-input bg-background px-3 py-2 text-sm font-mono text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40 motion-base"
              />
            </label>
            <label className="text-sm">
              <span className="text-muted">Current balance</span>
              <input
                inputMode="decimal"
                value={draft.currentBalance}
                onChange={(e) =>
                  setDraft({ ...draft, currentBalance: e.target.value })
                }
                onKeyDown={(e) => e.key === "Enter" && submit()}
                placeholder="34.89"
                className="mt-1 w-full border border-input bg-background px-3 py-2 text-sm font-mono text-foreground focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40 motion-base"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={!draft.name.trim()}
            className="mt-4 bg-primary px-4 py-2 text-sm font-medium text-primary-foreground motion-base hover:bg-primary-hover disabled:opacity-40"
          >
            Add card
          </button>
          <p className="mt-3 text-xs text-muted-foreground">
            Or drop that card&apos;s statement — the name, limit and balance are
            read from it.
          </p>
        </div>
      )}

      {ready && session.heldCards.length === 0 ? (
        <StatementDropzone />
      ) : (
        <>
          <div className="border border-border mb-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-3 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Card
                  </th>
                  <th className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Limit
                  </th>
                  <th className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Balance
                  </th>
                  <th className="px-4 py-3 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Used
                  </th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody>
                {session.heldCards.map((c) => {
                  const util =
                    c.creditLimit && c.creditLimit > 0
                      ? Math.max(0, c.currentBalance ?? 0) / c.creditLimit
                      : null;
                  return (
                    <tr key={c.id} className="border-b border-border last:border-0">
                      <td className="px-4 py-3 text-card-foreground">
                        {c.name}
                        {c.issuer && (
                          <span className="ml-2 text-xs text-muted-foreground capitalize">
                            {c.issuer}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <input
                          inputMode="decimal"
                          defaultValue={c.creditLimit ?? ""}
                          onBlur={(e) =>
                            updateCard(c.id, {
                              creditLimit: e.target.value
                                ? Number(e.target.value)
                                : undefined,
                            })
                          }
                          placeholder="—"
                          className="w-24 border border-transparent bg-transparent px-2 py-1 text-right font-mono tabular-nums text-card-foreground hover:border-border focus:border-ring focus:outline-none motion-base"
                        />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <input
                          inputMode="decimal"
                          defaultValue={c.currentBalance ?? ""}
                          onBlur={(e) =>
                            updateCard(c.id, {
                              currentBalance: e.target.value
                                ? Number(e.target.value)
                                : undefined,
                            })
                          }
                          placeholder="—"
                          className="w-24 border border-transparent bg-transparent px-2 py-1 text-right font-mono tabular-nums text-card-foreground hover:border-border focus:border-ring focus:outline-none motion-base"
                        />
                      </td>
                      <td
                        className={
                          "px-4 py-3 text-right font-mono tabular-nums " +
                          (util != null && util > 0.3
                            ? "text-destructive"
                            : "text-muted")
                        }
                      >
                        {util != null ? `${Math.round(util * 100)}%` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          type="button"
                          aria-label={`Remove ${c.name}`}
                          onClick={() => removeCard(c.id)}
                          className="text-muted-foreground hover:text-destructive motion-base"
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

          {gaps.length > 0 && (
            <section className="border border-border p-6 mb-6">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold text-card-foreground mb-1">
                    What each category could earn
                  </h2>
                  <p className="text-sm text-muted">
                    Your rate against the best card on the market, in
                    cash-equivalent terms — points are valued at what they
                    actually redeem for, not one cent each.
                  </p>
                </div>
                <div className="flex-shrink-0 text-right">
                  <div className="font-mono text-lg tabular-nums text-success">
                    +{formatCurrency(totalGain)}
                  </div>
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    per year on the table
                  </div>
                </div>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left">
                    <th className="pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Category
                    </th>
                    <th className="pb-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      A year
                    </th>
                    <th className="pb-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      You earn
                    </th>
                    <th className="pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Best card
                    </th>
                    <th className="pb-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Gain
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {gaps.map((g) => (
                    <tr key={g.category} className="border-b border-border last:border-0">
                      <td className="py-2.5 capitalize text-card-foreground">
                        {g.category}
                      </td>
                      <td className="py-2.5 text-right font-mono tabular-nums text-muted">
                        {formatCurrency(g.annual)}
                      </td>
                      <td className="py-2.5 text-right font-mono tabular-nums text-muted">
                        {g.heldRate}%
                      </td>
                      <td className="py-2.5">
                        <span className="text-card-foreground">{g.card.name}</span>
                        <span className="ml-2 text-xs text-muted-foreground">
                          {g.raw_rate}
                          {g.currency && g.currency !== "USD" ? "x" : "%"} ={" "}
                          {g.rate}%
                          {g.card.annualFee > 0
                            ? ` · $${g.card.annualFee}/yr`
                            : " · no fee"}
                        </span>
                      </td>
                      <td className="py-2.5 text-right font-mono tabular-nums text-success">
                        +{formatCurrency(g.gain)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-4 text-xs text-muted-foreground">
                Annual fees are shown but not subtracted: one card usually earns
                across several categories, so it has to be judged as a whole
                rather than per row. Recommendations does that, and ranks by
                first-year value net of fee.
              </p>
            </section>
          )}

          {best.length > 1 && session.heldCards.length > 1 && (
            <section className="border border-border p-6">
              <h2 className="font-semibold text-card-foreground mb-1">
                Which of your cards to use where
              </h2>
              <p className="text-sm text-muted mb-4">
                Among the cards you already hold.
              </p>
              <table className="w-full text-sm">
                <tbody>
                  {best.map((b) => (
                    <tr
                      key={b.category}
                      className="border-b border-border last:border-0"
                    >
                      <td className="py-2.5 capitalize text-muted">{b.category}</td>
                      <td className="py-2.5 text-card-foreground">
                        {b.best_card?.name ?? "—"}
                      </td>
                      <td className="py-2.5 text-right font-mono tabular-nums text-card-foreground">
                        {b.rate != null ? `${b.rate}×` : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </>
      )}
    </div>
  );
}

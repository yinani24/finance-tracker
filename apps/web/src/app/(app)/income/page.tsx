"use client";

import { useMemo } from "react";
import { Wallet, Info } from "lucide-react";
import { formatCurrency } from "@/lib/format";
import { useSession } from "@/lib/session/session-context";
import { summarize, monthlyTrend } from "@/lib/session/derive";
import { analyzeIncome, cadenceLabel } from "@/lib/session/income";
import { StatementDropzone } from "@/components/statement-dropzone";

/**
 * Income, read the same way spending is: out of an uploaded statement.
 *
 * This replaced the Accounts page, which listed bank connections the app no
 * longer makes. What was actually missing was the other side of the ledger — a
 * card statement shows what leaves, never what arrives, so nothing could say
 * whether spending was sustainable or whether an annual fee was affordable.
 * Dropping a bank or pay statement here fills that in: deposits are the
 * positive amounts, and the same parser handles them.
 */
export default function IncomePage() {
  const { session, ready } = useSession();
  const txns = session.transactions;

  const summary = useMemo(() => summarize(session), [session]);
  const trend = useMemo(() => monthlyTrend(txns), [txns]);
  const income = useMemo(() => analyzeIncome(txns), [txns]);
  const sources = income.sources;

  // Recurring income is projected from its own cadence rather than averaged
  // over the file's window: a bank export reaching back before the job starts
  // would otherwise report a fraction of the real salary.
  const monthlyIncome = income.monthlyTotal;
  const net = monthlyIncome - summary.monthlySpend;
  const savingsRate = monthlyIncome > 0 ? net / monthlyIncome : null;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">Income</h1>
        <p className="text-sm text-muted mt-1">
          Drop a bank or pay statement. Deposits are read the same way charges
          are — in this tab, never uploaded.
        </p>
      </div>

      {ready && sources.length === 0 ? (
        <>
          <StatementDropzone />
          <p className="mt-6 flex items-start gap-3 border border-border p-4 text-sm text-muted">
            <Info className="mt-0.5 h-4 w-4 flex-shrink-0 text-muted-foreground" />
            A credit-card statement only shows money going out. Adding a bank or
            pay statement is what lets this say whether your spending is
            sustainable, and whether a card&apos;s annual fee is worth paying.
          </p>
        </>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="border border-border p-6">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm text-muted">Monthly income</span>
                <Wallet className="w-5 h-5 text-muted-foreground" />
              </div>
              <span className="text-2xl font-semibold font-mono tabular-nums text-card-foreground">
                {formatCurrency(monthlyIncome)}
              </span>
              {income.primary && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {formatCurrency(income.annualTotal)} a year
                </p>
              )}
            </div>
            <div className="border border-border p-6">
              <span className="text-sm text-muted">Monthly spend</span>
              <div className="mt-2 text-2xl font-semibold font-mono tabular-nums text-card-foreground">
                {formatCurrency(summary.monthlySpend)}
              </div>
            </div>
            <div className="border border-border p-6">
              <span className="text-sm text-muted">Left over</span>
              <div
                className={
                  "mt-2 text-2xl font-semibold font-mono tabular-nums " +
                  (net < 0 ? "text-destructive" : "text-success")
                }
              >
                {formatCurrency(net)}
              </div>
              {savingsRate != null && (
                <p className="mt-1 text-xs text-muted-foreground">
                  {Math.round(savingsRate * 100)}% of income
                </p>
              )}
            </div>
          </div>

          <section className="border border-border p-6 mb-6">
            <h2 className="font-semibold text-card-foreground mb-4">
              Where it comes from
            </h2>
            <table className="w-full text-sm">
              <tbody>
                {sources.map((s) => (
                  <tr key={s.merchant} className="border-b border-border last:border-0">
                    <td className="py-2.5">
                      <span className="text-card-foreground">{s.merchant}</span>
                      {s.isRecurring ? (
                        <span className="ml-2 text-xs text-muted-foreground">
                          {formatCurrency(s.amount)} {cadenceLabel(s.cadence)} ·{" "}
                          {s.deposits}×
                        </span>
                      ) : (
                        <span className="ml-2 text-xs text-muted-foreground">
                          one-off · {s.deposits}×
                        </span>
                      )}
                    </td>
                    <td className="py-2.5 pl-3 text-right font-mono tabular-nums text-success">
                      {formatCurrency(s.annualized)}
                      <span className="ml-1 text-[11px] text-muted-foreground">
                        {s.isRecurring ? "/yr" : "seen"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {income.primary && (
              <p className="mt-4 text-sm text-muted">
                {income.primary.merchant} pays{" "}
                {formatCurrency(income.primary.amount)}{" "}
                {cadenceLabel(income.primary.cadence)} —{" "}
                {formatCurrency(income.primary.annualized)} a year. Projected
                from its own schedule, not averaged over the file.
              </p>
            )}
          </section>

          {trend.length > 1 && (
            <section className="border border-border p-6 mb-6">
              <h2 className="font-semibold text-card-foreground mb-4">
                In and out, by month
              </h2>
              <div className="space-y-3">
                {trend.map((m) => {
                  const max = Math.max(
                    ...trend.map((x) => Math.max(x.spend, x.income))
                  );
                  return (
                    <div key={m.month} className="text-sm">
                      <div className="flex items-baseline justify-between">
                        <span className="font-mono tabular-nums text-muted">
                          {m.month}
                        </span>
                        <span className="font-mono tabular-nums text-xs">
                          <span className="text-success">
                            +{formatCurrency(m.income)}
                          </span>
                          <span className="text-muted-foreground"> / </span>
                          <span className="text-card-foreground">
                            -{formatCurrency(m.spend)}
                          </span>
                        </span>
                      </div>
                      <div className="mt-1 space-y-0.5">
                        <div className="h-1.5 w-full bg-accent">
                          <div
                            className="h-1.5 bg-success motion-base"
                            style={{ width: `${max > 0 ? (m.income / max) * 100 : 0}%` }}
                          />
                        </div>
                        <div className="h-1.5 w-full bg-accent">
                          <div
                            className="h-1.5 bg-primary motion-base"
                            style={{ width: `${max > 0 ? (m.spend / max) * 100 : 0}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </section>
          )}

          <div className="border border-border p-6">
            <h2 className="font-semibold text-card-foreground mb-3">
              Add another statement
            </h2>
            <StatementDropzone compact />
          </div>
        </>
      )}
    </div>
  );
}

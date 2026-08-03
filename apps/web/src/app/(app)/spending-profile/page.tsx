"use client";

import { useMemo } from "react";
import Link from "next/link";
import { Repeat, ArrowRight } from "lucide-react";
import { formatCurrency } from "@/lib/format";
import { useSession } from "@/lib/session/session-context";
import {
  summarize,
  categoryTotals,
  topMerchants,
  detectSubscriptions,
  monthlyTrend,
} from "@/lib/session/derive";
import { StatementDropzone } from "@/components/statement-dropzone";

/**
 * The analysis the card advice is derived from.
 *
 * Everything here is computed from statements parsed in this tab — where the
 * money goes, which merchants take it, and what recurs every month whether or
 * not it is still wanted.
 */
export default function SpendingProfilePage() {
  const { session, ready } = useSession();
  const txns = session.transactions;

  const summary = useMemo(() => summarize(session), [session]);
  const cats = useMemo(() => categoryTotals(txns), [txns]);
  const merchants = useMemo(() => topMerchants(txns, 10), [txns]);
  const subs = useMemo(() => detectSubscriptions(txns), [txns]);
  const trend = useMemo(() => monthlyTrend(txns), [txns]);

  const subsMonthly = subs.reduce((s, x) => s + x.monthlyCost, 0);

  if (ready && txns.length === 0) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Spending profile
        </h1>
        <p className="text-sm text-muted mt-1 mb-8">
          Drop a statement and this builds itself.
        </p>
        <StatementDropzone />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Spending profile
        </h1>
        <p className="text-sm text-muted mt-1">
          {formatCurrency(summary.monthlySpend)} a month across{" "}
          {summary.transactionCount} transactions
          {summary.months > 1 ? ` over ${summary.months} months` : ""}
        </p>
      </div>

      {/* Subscriptions first: it is the section that most often changes
          behaviour, since a recurring charge is the easiest thing to cancel. */}
      <section className="border border-border p-6 mb-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div className="flex items-center gap-2">
            <Repeat className="w-5 h-5 text-muted-foreground" />
            <h2 className="font-semibold text-card-foreground">Subscriptions</h2>
          </div>
          {subs.length > 0 && (
            <div className="text-right">
              <div className="font-mono tabular-nums text-lg text-card-foreground">
                {formatCurrency(subsMonthly)}
              </div>
              <div className="text-xs text-muted-foreground">
                per month · {formatCurrency(subsMonthly * 12)}/yr
              </div>
            </div>
          )}
        </div>

        {subs.length === 0 ? (
          <p className="text-sm text-muted">
            No recurring charges found yet. A subscription is identified by
            repeat charges from the same merchant for a steady amount, so it
            takes at least two statements before one is visible.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Merchant
                </th>
                <th className="pb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Billing
                </th>
                <th className="pb-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Charge
                </th>
                <th className="pb-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Per month
                </th>
                <th className="pb-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Last seen
                </th>
              </tr>
            </thead>
            <tbody>
              {subs.map((s) => (
                <tr key={s.merchant} className="border-b border-border last:border-0">
                  <td className="py-2.5 text-card-foreground">{s.merchant}</td>
                  <td className="py-2.5 text-muted capitalize">
                    {s.period}
                    <span className="text-muted-foreground text-xs">
                      {" "}
                      · {s.charges}× · ~{s.cadenceDays}d
                    </span>
                  </td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-card-foreground">
                    {formatCurrency(s.amount)}
                  </td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-card-foreground">
                    {formatCurrency(s.monthlyCost)}
                  </td>
                  <td className="py-2.5 text-right font-mono tabular-nums text-muted">
                    {s.lastCharged}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <section className="border border-border p-6">
          <h2 className="font-semibold text-card-foreground mb-4">By category</h2>
          <div className="space-y-3">
            {cats.map((c) => (
              <div key={c.category}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="capitalize text-card-foreground">
                    {c.category}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {c.count}×
                    </span>
                  </span>
                  <span className="font-mono tabular-nums text-muted">
                    {formatCurrency(c.total)}
                    <span className="ml-2 text-xs text-muted-foreground">
                      {Math.round(c.share * 100)}%
                    </span>
                  </span>
                </div>
                <div className="mt-1 h-1 w-full bg-accent">
                  <div
                    className="h-1 bg-primary motion-base"
                    style={{ width: `${Math.max(c.share * 100, 1)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border border-border p-6">
          <h2 className="font-semibold text-card-foreground mb-4">Top merchants</h2>
          <table className="w-full text-sm">
            <tbody>
              {merchants.map((m) => (
                <tr key={m.merchant} className="border-b border-border last:border-0">
                  <td className="py-2 pr-3 text-card-foreground">{m.merchant}</td>
                  <td className="py-2 text-right text-xs text-muted-foreground font-mono tabular-nums">
                    {m.count}×
                  </td>
                  <td className="py-2 pl-3 text-right font-mono tabular-nums text-card-foreground">
                    {formatCurrency(m.total)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>

      {trend.length > 1 && (
        <section className="border border-border p-6 mb-6">
          <h2 className="font-semibold text-card-foreground mb-4">Month by month</h2>
          <div className="space-y-2">
            {trend.map((m) => {
              const max = Math.max(...trend.map((x) => x.spend));
              return (
                <div key={m.month} className="flex items-center gap-3 text-sm">
                  <span className="w-16 font-mono tabular-nums text-muted">
                    {m.month}
                  </span>
                  <div className="flex-1 h-2 bg-accent">
                    <div
                      className="h-2 bg-primary motion-base"
                      style={{ width: `${max > 0 ? (m.spend / max) * 100 : 0}%` }}
                    />
                  </div>
                  <span className="w-24 text-right font-mono tabular-nums text-card-foreground">
                    {formatCurrency(m.spend)}
                  </span>
                </div>
              );
            })}
          </div>
        </section>
      )}

      <Link
        href="/cards/recommendations"
        className="inline-flex items-center gap-2 bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground motion-base hover:bg-primary-hover"
      >
        See which card fits this <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}

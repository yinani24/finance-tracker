"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import {
  TrendingDown,
  Wallet,
  Gauge,
  Receipt,
  Lightbulb,
  ArrowRight,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { postStatelessRecommendations, hasApi } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { useSession } from "@/lib/session/session-context";
import { summarize, categoryTotals, topMerchants } from "@/lib/session/derive";
import { buildNarrative } from "@/lib/session/narrative";
import { StatementDropzone } from "@/components/statement-dropzone";

function StatCard({
  label,
  value,
  icon: Icon,
  trend,
  hint,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  trend?: "up" | "down" | "neutral";
  hint?: string;
}) {
  return (
    <div className="border border-border p-6">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted">{label}</span>
        <Icon className="w-5 h-5 text-muted-foreground" />
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-semibold tracking-tight text-card-foreground font-mono">
          {value}
        </span>
        {trend === "up" && <ArrowUpRight className="w-4 h-4 text-success mb-1" />}
        {trend === "down" && (
          <ArrowDownRight className="w-4 h-4 text-destructive mb-1" />
        )}
      </div>
      {hint && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}

export default function DashboardPage() {
  const { session, ready, setCredit } = useSession();
  const summary = useMemo(() => summarize(session), [session]);
  const cats = useMemo(() => categoryTotals(session.transactions), [session.transactions]);
  const merchants = useMemo(
    () => topMerchants(session.transactions, 6),
    [session.transactions]
  );
  const story = useMemo(() => buildNarrative(session), [session]);

  const hasData = ready && session.transactions.length > 0;

  // Ranking runs server-side against the public card dataset, but only on the
  // aggregates below — no merchant, date or amount detail is transmitted, and
  // nothing is stored.
  const { data: recommendations } = useQuery({
    queryKey: [
      "recommendations",
      "stateless",
      summary.monthlySpend,
      cats.map((c) => `${c.category}:${Math.round(c.total)}`).join(","),
      session.credit.scoreBand,
      session.heldCards.length,
    ],
    enabled: hasData && hasApi,
    queryFn: () =>
      postStatelessRecommendations({
        avg_monthly_spend: summary.monthlySpend,
        category_breakdown: Object.fromEntries(
          cats.map((c) => [c.category, c.total / summary.months])
        ),
        held_cards: session.heldCards.map((c) => ({
          // The dataset is keyed on the product name, not the display label.
          name: c.productName ?? c.name,
          issuer: c.issuer,
        })),
        credit_score_band: session.credit.scoreBand ?? null,
        recent_card_applications: session.credit.recentApplications ?? null,
      }),
  });

  if (ready && !hasData) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <div className="mb-8">
          <h1 className="text-2xl font-semibold text-card-foreground">Dashboard</h1>
          <p className="text-sm text-muted mt-1">
            Drop a statement and this fills in — nothing to set up first.
          </p>
        </div>
        <StatementDropzone />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">Dashboard</h1>
        <p className="text-sm text-muted mt-1">
          {summary.transactionCount} transactions
          {summary.periodStart && summary.periodEnd
            ? ` · ${summary.periodStart} to ${summary.periodEnd}`
            : ""}
        </p>
      </div>

      {/* The summary in words, before the same facts as figures. Reading a
          sentence is less work than reading a table, and the two can't
          disagree because both come from the same derived values. */}
      <section className="mb-8 max-w-3xl">
        <p className="text-lg leading-relaxed text-card-foreground">
          {story.headline}
        </p>
        {story.points.length > 0 && (
          <ul className="mt-4 space-y-2">
            {story.points.map((point, i) => (
              <li key={i} className="flex gap-3 text-[15px] leading-relaxed text-muted">
                <span aria-hidden className="mt-2 h-px w-4 flex-shrink-0 bg-border" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        )}
        {story.suggestion && (
          <p className="mt-4 border-l-2 border-primary pl-4 text-[15px] leading-relaxed text-card-foreground">
            {story.suggestion}
          </p>
        )}
      </section>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Monthly spend"
          value={formatCurrency(summary.monthlySpend)}
          icon={TrendingDown}
          hint={
            summary.months > 1 ? `Averaged over ${summary.months} months` : undefined
          }
        />
        <StatCard
          label="Total spend"
          value={formatCurrency(summary.totalSpend)}
          icon={Receipt}
        />
        <StatCard
          label="Top category"
          value={summary.topCategory ? summary.topCategory.category : "—"}
          icon={Wallet}
          hint={
            summary.topCategory
              ? `${formatCurrency(summary.topCategory.total)} · ${Math.round(
                  summary.topCategory.share * 100
                )}% of spend`
              : undefined
          }
        />
        <StatCard
          label="Utilization"
          value={
            summary.utilization != null
              ? `${Math.round(summary.utilization * 100)}%`
              : "—"
          }
          icon={Gauge}
          trend={summary.utilization != null && summary.utilization > 0.3 ? "down" : undefined}
          hint={
            summary.creditLimit
              ? `${formatCurrency(summary.currentBalance ?? 0)} of ${formatCurrency(summary.creditLimit)}`
              : undefined
          }
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <section className="border border-border p-6">
          <h2 className="font-semibold text-card-foreground mb-4">Where it goes</h2>
          <div className="space-y-3">
            {cats.slice(0, 6).map((c) => (
              <div key={c.category}>
                <div className="flex items-baseline justify-between text-sm">
                  <span className="capitalize text-card-foreground">{c.category}</span>
                  <span className="font-mono tabular-nums text-muted">
                    {formatCurrency(c.total)}
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
          <Link
            href="/transactions"
            className="mt-5 inline-flex items-center gap-1 text-sm text-muted hover:text-card-foreground motion-base"
          >
            All transactions <ArrowRight className="h-3.5 w-3.5" />
          </Link>
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

      {recommendations?.recommendations && recommendations.recommendations.length > 0 && (
        <div className="border border-border p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-muted-foreground" />
              <h2 className="font-semibold text-card-foreground">Top card picks</h2>
            </div>
            <div className="flex items-center gap-3">
              {/* Credit standing lives with what it affects: it re-ranks these
                  picks by expected value. Optional — blank ranks on value. */}
              <label className="flex items-center gap-2 text-xs text-muted">
                Credit
                <select
                  value={session.credit.scoreBand ?? ""}
                  onChange={(e) =>
                    setCredit({
                      scoreBand: (e.target.value || undefined) as
                        | "excellent"
                        | "good"
                        | "fair"
                        | "poor"
                        | undefined,
                    })
                  }
                  className="border border-input bg-background text-foreground px-2 py-1 text-xs motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
                >
                  <option value="">Not set</option>
                  <option value="excellent">Excellent (740+)</option>
                  <option value="good">Good (670–739)</option>
                  <option value="fair">Fair (580–669)</option>
                  <option value="poor">Poor (&lt;580)</option>
                </select>
              </label>
              <Link
                href="/cards/recommendations"
                className="text-sm text-muted hover:text-card-foreground motion-base"
              >
                View all &rarr;
              </Link>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.recommendations.slice(0, 4).map((rec, i) => (
              <Link key={rec.card.cardId} href="/cards/recommendations" className="panel-link">
                <div className="panel">
                  <div className="panel-head">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-mono text-muted">{i + 1}.</span>
                      <span className="font-medium text-[15px] text-card-foreground truncate">
                        {rec.card.name}
                      </span>
                    </span>
                    <ArrowRight className="hover-arrow w-4 h-4 flex-shrink-0 text-muted" />
                  </div>
                  <div className="panel-body">
                    <div className="panel-row">
                      <span className="panel-label">Issuer</span>
                      <span className="panel-value truncate">{rec.card.issuer}</span>
                    </div>
                    <div className="panel-row">
                      <span className="panel-label">Annual fee</span>
                      <span className="panel-value font-mono">
                        {rec.card.annualFee ? `$${rec.card.annualFee}` : "None"}
                      </span>
                    </div>
                    <div className="panel-row">
                      <span className="panel-label">Est. first-year value</span>
                      <span className="mono-chip !bg-success/10 !text-success">
                        ~${Math.round(rec.score).toLocaleString()}
                      </span>
                    </div>
                    {rec.approval_label && (
                      <div className="panel-row">
                        <span className="panel-label">Approval odds</span>
                        <span
                          className="mono-chip capitalize"
                          title={rec.approval_reason ?? undefined}
                        >
                          {rec.approval_label}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, TrendingUp, CircleAlert, Check } from "lucide-react";
import { postStatelessPortfolio } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { useSession } from "@/lib/session/session-context";
import { summarize, categoryTotals } from "@/lib/session/derive";
import { buildInsights, type Insight } from "@/lib/session/insights";
import { StatementDropzone } from "@/components/statement-dropzone";

/**
 * What the other pages can't see on their own.
 *
 * This used to wrap the recommendation engine, so every item it produced was
 * already a page in the nav. It now reports the cross-cutting findings:
 * recurring charges, utilization, cashflow, and category spend sitting on the
 * wrong card — each with the numbers it came from.
 */

const SEVERITY: Record<
  Insight["severity"],
  { icon: React.ElementType; className: string; label: string }
> = {
  critical: {
    icon: AlertTriangle,
    className: "text-destructive",
    label: "Needs attention",
  },
  warning: { icon: CircleAlert, className: "text-destructive", label: "Worth fixing" },
  opportunity: { icon: TrendingUp, className: "text-success", label: "Opportunity" },
};

export default function InsightsPage() {
  const { session, ready } = useSession();

  const summary = useMemo(() => summarize(session), [session]);
  const cats = useMemo(
    () => categoryTotals(session.transactions),
    [session.transactions]
  );

  const hasData = ready && session.transactions.length > 0;

  // Per-category rates for the held cards, so a "wrong card" finding can be
  // priced rather than merely asserted.
  const { data } = useQuery({
    queryKey: [
      "portfolio",
      "stateless",
      session.heldCards.map((c) => c.name).join(","),
      Math.round(summary.monthlySpend),
    ],
    enabled: hasData && session.heldCards.length > 0,
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

  const insights = useMemo(
    () => buildInsights(session, data?.best_per_category ?? []),
    [session, data]
  );

  const totalUpside = insights
    .filter((i) => i.impactAnnual != null && i.impactAnnual > 0)
    .reduce((s, i) => s + (i.impactAnnual ?? 0), 0);

  if (ready && !hasData) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        <h1 className="text-2xl font-semibold text-card-foreground">Insights</h1>
        <p className="text-sm text-muted mt-1 mb-8">
          Drop a statement and this finds what the other pages can&apos;t see on
          their own.
        </p>
        <StatementDropzone />
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">Insights</h1>
        <p className="text-sm text-muted mt-1">
          {insights.length === 0
            ? "Nothing worth flagging in what's loaded."
            : totalUpside > 0
              ? `${insights.length} finding${insights.length === 1 ? "" : "s"} · up to ${formatCurrency(totalUpside)} a year in play`
              : `${insights.length} finding${insights.length === 1 ? "" : "s"}`}
        </p>
      </div>

      {insights.length === 0 ? (
        <div className="border border-border p-8 text-center">
          <Check className="mx-auto mb-3 h-8 w-8 text-success opacity-70" />
          <p className="text-sm text-muted">
            No recurring charges, utilization or cashflow problems found in the
            statements loaded. Adding more months gives this more to work with.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {insights.map((insight) => {
            const s = SEVERITY[insight.severity];
            const Icon = s.icon;
            return (
              <article key={insight.id} className="border border-border p-6">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex min-w-0 gap-3">
                    <Icon className={`mt-0.5 h-5 w-5 flex-shrink-0 ${s.className}`} />
                    <div className="min-w-0">
                      <h2 className="font-semibold text-card-foreground">
                        {insight.title}
                      </h2>
                      <p className="mt-1 text-sm text-muted">{insight.body}</p>
                    </div>
                  </div>
                  {insight.impactAnnual != null && (
                    <div className="flex-shrink-0 text-right">
                      <div
                        className={
                          "font-mono text-lg tabular-nums " +
                          (insight.impactAnnual < 0
                            ? "text-destructive"
                            : "text-success")
                        }
                      >
                        {insight.impactAnnual < 0 ? "−" : ""}
                        {formatCurrency(Math.abs(insight.impactAnnual))}
                      </div>
                      <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                        per year
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border pt-3 text-xs">
                  {insight.evidence.map((e, i) => (
                    <span key={i} className="text-muted-foreground">
                      {e.label}{" "}
                      <span className="font-mono tabular-nums text-card-foreground">
                        {e.value}
                      </span>
                    </span>
                  ))}
                  <span className="ml-auto text-muted-foreground capitalize">
                    {insight.effort} effort
                  </span>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

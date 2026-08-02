"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Sparkles, ArrowRight } from "lucide-react";
import { getInsights, getInsightsSummary } from "@/lib/api";
import { formatCurrency } from "@/lib/format";

function formatImpact(oneTime: number, annual: number): string {
  if (annual !== 0) return `${formatCurrency(annual / 100)}/yr`;
  if (oneTime !== 0) return formatCurrency(oneTime / 100);
  return "—";
}

export function InsightsWidget() {
  const { data: insights } = useQuery({
    queryKey: ["insights", "all"],
    queryFn: () => getInsights({ limit: 3 }),
  });
  const { data: summary } = useQuery({
    queryKey: ["insights-summary"],
    queryFn: getInsightsSummary,
  });

  if (!insights || insights.length === 0) return null;

  return (
    <div className="bg-card rounded-xl border border-border p-6 mb-8">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-link" />
          <h2 className="font-semibold text-card-foreground">Insights</h2>
          {summary && summary.unread_count > 0 && (
            <span className="rounded-full bg-primary/15 px-2 py-0.5 text-xs text-link">
              {summary.unread_count} new
            </span>
          )}
        </div>
        <Link
          href="/insights"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-card-foreground motion-base"
        >
          View all <ArrowRight className="w-3.5 h-3.5" />
        </Link>
      </div>

      {summary && summary.total_annual_impact_cents > 0 && (
        <p className="mb-4 text-xs text-muted">
          Potential annual impact:{" "}
          <span className="font-mono text-card-foreground">
            {formatCurrency(summary.total_annual_impact_cents / 100)}
          </span>
        </p>
      )}

      <div className="space-y-3">
        {insights.slice(0, 3).map((ins) => (
          <Link
            key={ins.id}
            href="/insights"
            className="block rounded-lg border border-border p-4 hover:border-primary/40 motion-base"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-wide text-muted">
                  {ins.engine}
                </p>
                <p className="font-medium text-sm text-card-foreground truncate">
                  {ins.title}
                </p>
                <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                  {ins.body}
                </p>
              </div>
              <span className="font-mono text-xs text-card-foreground shrink-0">
                {formatImpact(ins.impact_one_time_cents, ins.impact_annual_cents)}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

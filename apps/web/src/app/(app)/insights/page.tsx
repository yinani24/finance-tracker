"use client";

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  dismissInsight,
  getInsights,
  getInsightsSummary,
  markInsightActedOn,
  markInsightsSeen,
  snoozeInsight,
} from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import type { Insight } from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  Sparkles,
  XCircle,
} from "lucide-react";

const ENGINE_TABS = [
  { id: "all", label: "All", engine: undefined },
  { id: "save", label: "Save", engine: "save" },
  { id: "earn", label: "Earn", engine: "earn" },
  { id: "goal_forecast", label: "Goals", engine: "goal_forecast" },
  { id: "card", label: "Cards", engine: "card" },
] as const;

const EFFORT_LABELS: Record<string, string> = {
  one_click: "1-click",
  quick: "Quick",
  moderate: "Moderate",
  heavy: "Heavy",
};

function formatImpact(oneTime: number, annual: number): string {
  if (annual !== 0) return `${formatCurrency(annual / 100)}/yr`;
  if (oneTime !== 0) return formatCurrency(oneTime / 100);
  return "—";
}

function EffortBadge({ effort }: { effort: string }) {
  return (
    <span className="inline-flex items-center rounded-full bg-accent px-2 py-0.5 text-xs text-muted">
      {EFFORT_LABELS[effort] ?? effort}
    </span>
  );
}

function InsightRow({ insight }: { insight: Insight }) {
  const qc = useQueryClient();
  const [expanded, setExpanded] = useState(false);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["insights"] });
    qc.invalidateQueries({ queryKey: ["insights-summary"] });
  };

  const dismissMut = useMutation({
    mutationFn: () => dismissInsight(insight.id),
    onSuccess: invalidate,
  });
  const snoozeMut = useMutation({
    mutationFn: (days: number) => {
      const until = new Date();
      until.setDate(until.getDate() + days);
      return snoozeInsight(insight.id, until.toISOString());
    },
    onSuccess: invalidate,
  });
  const actedMut = useMutation({
    mutationFn: () => markInsightActedOn(insight.id),
    onSuccess: invalidate,
  });

  let dataPoints: Array<{ label: string; value: string }> = [];
  try {
    const parsed = JSON.parse(insight.evidence_json || "{}");
    if (Array.isArray(parsed.data_points)) dataPoints = parsed.data_points;
  } catch {
    dataPoints = [];
  }

  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs uppercase tracking-wide text-muted">
              {insight.engine}
            </span>
            <EffortBadge effort={insight.effort} />
            {!insight.seen_at && (
              <span className="inline-flex items-center rounded-full bg-primary/15 px-2 py-0.5 text-xs text-link">
                New
              </span>
            )}
          </div>
          <h3 className="text-base font-medium text-card-foreground">
            {insight.title}
          </h3>
          <p className="mt-1 text-sm text-muted">{insight.body}</p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-xs text-muted">Impact</p>
          <p className="font-mono text-base font-semibold text-card-foreground">
            {formatImpact(insight.impact_one_time_cents, insight.impact_annual_cents)}
          </p>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <button
          onClick={() => actedMut.mutate()}
          disabled={actedMut.isPending}
          className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
        >
          <CheckCircle className="w-3.5 h-3.5" /> Mark done
        </button>
        <button
          onClick={() => snoozeMut.mutate(7)}
          disabled={snoozeMut.isPending}
          className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
        >
          <Clock className="w-3.5 h-3.5" /> Snooze 7d
        </button>
        <button
          onClick={() => dismissMut.mutate()}
          disabled={dismissMut.isPending}
          className="inline-flex items-center gap-1 rounded-lg border border-border bg-background px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
        >
          <XCircle className="w-3.5 h-3.5" /> Dismiss
        </button>
        {dataPoints.length > 0 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="ml-auto inline-flex items-center gap-1 text-xs text-muted hover:text-card-foreground"
          >
            {expanded ? "Hide" : "Details"}
            {expanded ? (
              <ChevronUp className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown className="w-3.5 h-3.5" />
            )}
          </button>
        )}
      </div>

      {expanded && dataPoints.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-3 rounded-xl bg-accent p-4 md:grid-cols-3">
          {dataPoints.map((dp, i) => (
            <div key={i}>
              <p className="text-xs text-muted">{dp.label}</p>
              <p className="font-mono text-sm text-card-foreground">{dp.value}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function InsightsPage() {
  const [tab, setTab] = useState<(typeof ENGINE_TABS)[number]["id"]>("all");
  const qc = useQueryClient();
  const activeTab = ENGINE_TABS.find((t) => t.id === tab)!;

  const { data: insights, isLoading } = useQuery({
    queryKey: ["insights", activeTab.engine ?? "all"],
    queryFn: () => getInsights({ engine: activeTab.engine }),
  });
  const { data: summary } = useQuery({
    queryKey: ["insights-summary"],
    queryFn: getInsightsSummary,
  });

  useEffect(() => {
    markInsightsSeen()
      .then(() => qc.invalidateQueries({ queryKey: ["insights-summary"] }))
      .catch(() => {});
  }, [qc]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-8">
      <div className="mb-6 flex items-center gap-3">
        <Sparkles className="w-5 h-5 text-link" />
        <h1 className="text-2xl font-semibold tracking-tight">Insights</h1>
      </div>

      {summary && (
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-xs text-muted">Active</p>
            <p className="mt-1 font-mono text-2xl font-semibold text-card-foreground">
              {summary.total_active}
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-xs text-muted">Annual impact</p>
            <p className="mt-1 font-mono text-2xl font-semibold text-card-foreground">
              {formatCurrency(summary.total_annual_impact_cents / 100)}
            </p>
          </div>
          <div className="rounded-2xl border border-border bg-card p-5">
            <p className="text-xs text-muted">Unread</p>
            <p className="mt-1 font-mono text-2xl font-semibold text-card-foreground">
              {summary.unread_count}
            </p>
          </div>
        </div>
      )}

      <div className="mb-6 flex gap-2 overflow-x-auto">
        {ENGINE_TABS.map((t) => {
          const count = t.engine ? summary?.by_engine[t.engine] ?? 0 : summary?.total_active ?? 0;
          const active = t.id === tab;
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`rounded-full px-4 py-1.5 text-sm motion-base ${
                active
                  ? "bg-primary text-primary-foreground"
                  : "border border-border bg-background text-muted hover:text-card-foreground"
              }`}
            >
              {t.label}
              {summary && (
                <span className="ml-2 text-xs opacity-70">{count}</span>
              )}
            </button>
          );
        })}
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32 w-full rounded-2xl" />
          ))}
        </div>
      ) : !insights || insights.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border bg-card p-12 text-center">
          <p className="text-sm text-muted">No insights here yet. Check back after your next sync.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {insights.map((ins) => (
            <InsightRow key={ins.id} insight={ins} />
          ))}
        </div>
      )}
    </div>
  );
}

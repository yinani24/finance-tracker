"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAccounts,
  getTransactions,
  getGoals,
  getNextCardRecommendations,
  getPreferences,
  updatePreferences,
} from "@/lib/api";
import type { UserPreference } from "@/lib/types";
import { formatCurrency } from "@/lib/format";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Lightbulb,
  ArrowRight,
} from "lucide-react";
import { InsightsWidget } from "@/components/insights-widget";
import Link from "next/link";

function StatCard({
  label,
  value,
  icon: Icon,
  trend,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  trend?: "up" | "down" | "neutral";
}) {
  return (
    <div className="bg-card rounded-xl border border-border p-6">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted">{label}</span>
        <Icon className="w-5 h-5 text-muted-foreground" />
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-semibold tracking-tight text-card-foreground font-mono">
          {value}
        </span>
        {trend === "up" && (
          <ArrowUpRight className="w-4 h-4 text-success mb-1" />
        )}
        {trend === "down" && (
          <ArrowDownRight className="w-4 h-4 text-destructive mb-1" />
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });
  const { data: transactions = [] } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => getTransactions(),
  });
  const { data: goals = [] } = useQuery({
    queryKey: ["goals"],
    queryFn: getGoals,
  });
  const { data: recommendations } = useQuery({
    queryKey: ["recommendations", "next-card"],
    queryFn: getNextCardRecommendations,
  });
  const { data: prefs } = useQuery({
    queryKey: ["preferences"],
    queryFn: getPreferences,
  });
  const queryClient = useQueryClient();
  const prefsMutation = useMutation({
    mutationFn: (data: Partial<UserPreference>) => updatePreferences(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["preferences"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  const netWorth = accounts.reduce((sum, a) => sum + a.balance, 0);
  const totalIncome = transactions
    .filter((t) => t.is_income)
    .reduce((sum, t) => sum + t.amount, 0);
  const totalExpenses = transactions
    .filter((t) => !t.is_income)
    .reduce((sum, t) => sum + Math.abs(t.amount), 0);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Dashboard
        </h1>
        <p className="text-sm text-muted mt-1">Your financial overview</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Net Worth"
          value={formatCurrency(netWorth)}
          icon={Wallet}
          trend="up"
        />
        <StatCard
          label="Income"
          value={formatCurrency(totalIncome)}
          icon={TrendingUp}
          trend="up"
        />
        <StatCard
          label="Expenses"
          value={formatCurrency(totalExpenses)}
          icon={TrendingDown}
          trend="down"
        />
        <StatCard
          label="Active Goals"
          value={String(goals.length)}
          icon={Target}
        />
      </div>

      <InsightsWidget />

      {recommendations?.recommendations && recommendations.recommendations.length > 0 && (
        <div className="bg-card rounded-xl border border-border p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Lightbulb className="w-5 h-5 text-muted-foreground" />
              <h2 className="font-semibold text-card-foreground">Top Card Picks</h2>
            </div>
            <div className="flex items-center gap-3">
              {/* Credit standing lives with what it affects: it re-ranks these
                  picks by expected value. Optional — blank ranks on value. */}
              <label className="flex items-center gap-2 text-xs text-muted">
                Credit
                <select
                  value={prefs?.credit_score_band ?? ""}
                  onChange={(e) =>
                    prefsMutation.mutate({
                      credit_score_band: e.target.value || null,
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
            {recommendations.recommendations.slice(0, 5).map((rec, i) => (
              <Link
                key={rec.card.cardId}
                href="/cards/recommendations"
                className="panel-link"
              >
                <div className="panel">
                  <div className="panel-head">
                    <span className="flex items-center gap-2 min-w-0">
                      <span className="text-xs font-mono text-muted">
                        {i + 1}.
                      </span>
                      <span className="font-medium text-[15px] text-card-foreground truncate">
                        {rec.card.name}
                      </span>
                    </span>
                    <ArrowRight className="hover-arrow w-4 h-4 flex-shrink-0 text-muted" />
                  </div>
                  <div className="panel-body">
                    <div className="panel-row">
                      <span className="panel-label">Issuer</span>
                      <span className="panel-value truncate">
                        {rec.card.issuer}
                      </span>
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
      {/* AI Financial Assistant removed from the dashboard for now.
          Component kept at @/components/chat — re-add <Chat /> to restore. */}
    </div>
  );
}

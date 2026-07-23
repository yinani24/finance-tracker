"use client";

import { useQuery } from "@tanstack/react-query";
import { getAccounts, getTransactions, getGoals, getNextCardRecommendations } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Lightbulb,
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
          <ArrowUpRight className="w-4 h-4 text-emerald-500 mb-1" />
        )}
        {trend === "down" && (
          <ArrowDownRight className="w-4 h-4 text-red-500 mb-1" />
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
            <Link
              href="/cards/recommendations"
              className="text-sm text-muted hover:text-card-foreground transition-colors"
            >
              View all &rarr;
            </Link>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {recommendations.recommendations.slice(0, 5).map((rec, i) => (
              <div key={rec.card.cardId} className="rounded-lg border border-border p-4">
                <div className="flex items-start justify-between mb-2 gap-2">
                  <div className="flex items-start gap-2 min-w-0">
                    <span className="text-xs font-mono text-muted mt-0.5">
                      {i + 1}.
                    </span>
                    <div className="min-w-0">
                      <p className="font-medium text-sm text-card-foreground truncate">
                        {rec.card.name}
                      </p>
                      <p className="text-xs text-muted">
                        {rec.card.issuer}
                        {rec.card.annualFee
                          ? ` · $${rec.card.annualFee}/yr`
                          : " · no annual fee"}
                      </p>
                    </div>
                  </div>
                  <span className="whitespace-nowrap text-xs font-mono bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded">
                    ~${Math.round(rec.score).toLocaleString()} · 1st yr
                  </span>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-2">{rec.explanation}</p>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* AI Financial Assistant removed from the dashboard for now.
          Component kept at @/components/chat — re-add <Chat /> to restore. */}
    </div>
  );
}

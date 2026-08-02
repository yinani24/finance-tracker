"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getNextCardRecommendations,
  getPortfolioAnalysis,
  getSpendingProfile,
  refreshRecommendations,
} from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { useState } from "react";
import {
  Lightbulb,
  RefreshCw,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  ExternalLink,
  PieChart,
  Utensils,
  Store,
} from "lucide-react";

function NextCardTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "next-card"],
    queryFn: getNextCardRecommendations,
  });

  if (isLoading) {
    return <div className="text-muted text-sm">Analyzing your spending...</div>;
  }

  const recs = data?.recommendations ?? [];

  if (recs.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        <Lightbulb className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p>
          No recommendations yet. Add more transactions to get personalized
          suggestions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {recs.map((rec) => (
        <div
          key={rec.card.cardId}
          className="bg-card rounded-xl border border-border p-6"
        >
          <div className="flex items-start justify-between mb-3">
            <div>
              <h3 className="font-semibold text-card-foreground">
                {rec.card.name}
              </h3>
              <p className="text-sm text-muted">
                {rec.card.issuer} &middot; {rec.card.network}
              </p>
            </div>
            {rec.card.url && (
              <a
                href={rec.card.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-muted-foreground hover:text-card-foreground transition-colors"
              >
                <ExternalLink className="w-4 h-4" />
              </a>
            )}
          </div>

          <div className="flex gap-4 mb-3 text-sm">
            <div>
              <span className="text-muted">Bonus:</span>{" "}
              <span className="font-mono font-medium text-card-foreground">
                {formatCurrency(rec.bonus_value)}
              </span>
            </div>
            <div>
              <span className="text-muted">Time to hit:</span>{" "}
              <span className="font-mono text-card-foreground">
                ~{Math.ceil(rec.months_to_hit)} mo
              </span>
            </div>
            <div>
              <span className="text-muted">1st-yr value:</span>{" "}
              <span className="font-mono text-card-foreground">
                {formatCurrency(rec.score)}
              </span>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">{rec.explanation}</p>

          {rec.card.annualFee > 0 && (
            <div className="mt-2 text-xs text-muted">
              Annual fee: {formatCurrency(rec.card.annualFee)}
              {rec.card.isAnnualFeeWaived && " (waived first year)"}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function PortfolioTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "portfolio"],
    queryFn: getPortfolioAnalysis,
  });

  if (isLoading) {
    return (
      <div className="text-muted text-sm">Analyzing your portfolio...</div>
    );
  }

  const cards = data?.cards ?? [];

  if (cards.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        <Lightbulb className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p>Add your credit cards to get a portfolio analysis.</p>
      </div>
    );
  }

  const statusIcon = {
    good: <CheckCircle className="w-5 h-5 text-success" />,
    underperforming: <AlertTriangle className="w-5 h-5 text-amber-500" />,
    costing_money: <AlertTriangle className="w-5 h-5 text-destructive" />,
  };

  return (
    <div className="space-y-4">
      {cards.map((card, i) => (
        <div
          key={i}
          className="bg-card rounded-xl border border-border p-6"
        >
          <div className="flex items-start gap-3 mb-3">
            {statusIcon[card.status]}
            <div>
              <h3 className="font-semibold text-card-foreground">
                {String(card.user_card.name ?? "Card")}
              </h3>
              <p className="text-sm text-muted">
                {String(card.user_card.network ?? "")}
              </p>
            </div>
          </div>

          <div className="flex gap-4 mb-3 text-sm">
            <div>
              <span className="text-muted">Annual fee:</span>{" "}
              <span className="font-mono text-card-foreground">
                {formatCurrency(Number(card.user_card.annual_fee ?? 0))}
              </span>
            </div>
            <div>
              <span className="text-muted">Est. value:</span>{" "}
              <span className="font-mono text-card-foreground">
                {formatCurrency(card.estimated_annual_value)}
              </span>
            </div>
            <div>
              <span className="text-muted">Net:</span>{" "}
              <span
                className={`font-mono font-medium ${card.net_value >= 0 ? "text-success" : "text-destructive"}`}
              >
                {formatCurrency(card.net_value)}
              </span>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">{card.explanation}</p>

          {card.alternatives.length > 0 && (
            <div className="mt-4 pt-3 border-t border-border">
              <p className="text-xs font-medium text-muted mb-2">
                Better alternatives:
              </p>
              <div className="space-y-2">
                {card.alternatives.slice(0, 3).map((alt, j) => (
                  <div
                    key={j}
                    className="flex items-center justify-between text-sm"
                  >
                    <div>
                      <span className="text-card-foreground">
                        {alt.card.name}
                      </span>
                      <span className="text-muted ml-2">
                        {alt.card.issuer}
                      </span>
                    </div>
                    <div className="flex gap-3 text-xs">
                      <span className="text-muted">
                        Fee: {formatCurrency(alt.card.annualFee)}
                      </span>
                      <span className="text-success font-mono">
                        Net: {formatCurrency(alt.net_value)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function formatCategoryName(category: string): string {
  return category
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function SpendingTab() {
  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "spending-profile"],
    queryFn: getSpendingProfile,
  });

  if (isLoading) {
    return <div className="text-muted text-sm">Analyzing your spending...</div>;
  }

  const categories = data?.categories ?? [];

  if (categories.length === 0) {
    return (
      <div className="text-center py-12 text-muted">
        <PieChart className="w-8 h-8 mx-auto mb-3 opacity-50" />
        <p>Add or sync transactions to see your spending profile.</p>
      </div>
    );
  }

  // Dining first (the headline habit metric), then by monthly spend descending.
  const ordered = [...categories].sort((a, b) => {
    if (a.category === "dining") return -1;
    if (b.category === "dining") return 1;
    return b.monthly_avg - a.monthly_avg;
  });
  const maxSpend = Math.max(...ordered.map((c) => c.monthly_avg), 1);

  const dining = data?.dining ?? null;
  const topMerchants = data?.top_merchants ?? [];

  return (
    <div className="space-y-6">
      {dining && (
        <div className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-center gap-3">
            <Utensils className="w-5 h-5 text-amber-500" />
            <div>
              <p className="text-sm text-muted">You dine out about</p>
              <p className="text-2xl font-semibold text-card-foreground">
                {dining.monthly_avg_count.toLocaleString()}
                <span className="text-base font-normal text-muted">
                  {" "}
                  &times;/month
                </span>
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                {formatCurrency(dining.monthly_avg)}/mo &middot;{" "}
                {formatCurrency(dining.avg_per_txn)} per visit
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="bg-card rounded-xl border border-border p-6">
        <h3 className="font-semibold text-card-foreground mb-1">
          Monthly spending by category
        </h3>
        {data && (
          <p className="text-xs text-muted mb-4">
            {formatCurrency(data.avg_monthly_spend)}/mo average across all
            categories
          </p>
        )}
        <div className="space-y-3">
          {ordered.map((cat) => (
            <div key={cat.category}>
              <div className="flex items-center justify-between text-sm mb-1">
                <span className="text-card-foreground">
                  {formatCategoryName(cat.category)}
                </span>
                <span className="font-mono text-card-foreground">
                  {formatCurrency(cat.monthly_avg)}/mo
                </span>
              </div>
              <div className="h-2 rounded-full bg-muted/40 overflow-hidden">
                <div
                  className="h-full rounded-full bg-success"
                  style={{
                    width: `${Math.max(2, (cat.monthly_avg / maxSpend) * 100)}%`,
                  }}
                />
              </div>
              <p className="text-xs text-muted mt-1">
                {cat.monthly_avg_count.toLocaleString()} txns/mo &middot;{" "}
                {formatCurrency(cat.avg_per_txn)} avg
              </p>
            </div>
          ))}
        </div>
      </div>

      {topMerchants.length > 0 && (
        <div className="bg-card rounded-xl border border-border p-6">
          <div className="flex items-center gap-2 mb-4">
            <Store className="w-4 h-4 text-muted" />
            <h3 className="font-semibold text-card-foreground">Top merchants</h3>
          </div>
          <div className="space-y-2">
            {topMerchants.map((m) => (
              <div
                key={m.merchant}
                className="flex items-center justify-between text-sm"
              >
                <span className="text-card-foreground">{m.merchant}</span>
                <span className="font-mono text-muted-foreground">
                  {formatCurrency(m.monthly_avg)}/mo
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function RecommendationsPage() {
  const [tab, setTab] = useState<"next-card" | "portfolio" | "spending">(
    "next-card",
  );
  const queryClient = useQueryClient();

  const refreshMutation = useMutation({
    mutationFn: refreshRecommendations,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  return (
    <div>
      <div className="flex items-center justify-end mb-6">
        <button
          onClick={() => refreshMutation.mutate()}
          disabled={refreshMutation.isPending}
          className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-border hover:bg-accent/50 transition-colors disabled:opacity-50"
        >
          <RefreshCw
            className={`w-4 h-4 ${refreshMutation.isPending ? "animate-spin" : ""}`}
          />
          Refresh
        </button>
      </div>

      <div className="flex gap-1 mb-6 bg-muted/30 rounded-lg p-1">
        <button
          onClick={() => setTab("next-card")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "next-card"
              ? "bg-card text-card-foreground shadow-sm"
              : "text-muted hover:text-card-foreground"
          }`}
        >
          <TrendingUp className="w-4 h-4" />
          Next Card
        </button>
        <button
          onClick={() => setTab("portfolio")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "portfolio"
              ? "bg-card text-card-foreground shadow-sm"
              : "text-muted hover:text-card-foreground"
          }`}
        >
          <Lightbulb className="w-4 h-4" />
          Portfolio Analysis
        </button>
        <button
          onClick={() => setTab("spending")}
          className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 text-sm rounded-md transition-colors ${
            tab === "spending"
              ? "bg-card text-card-foreground shadow-sm"
              : "text-muted hover:text-card-foreground"
          }`}
        >
          <PieChart className="w-4 h-4" />
          Spending Profile
        </button>
      </div>

      {tab === "next-card" ? (
        <NextCardTab />
      ) : tab === "portfolio" ? (
        <PortfolioTab />
      ) : (
        <SpendingTab />
      )}
    </div>
  );
}

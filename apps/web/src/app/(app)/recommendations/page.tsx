"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getNextCardRecommendations,
  getPortfolioAnalysis,
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
                {rec.bonus_value.toLocaleString()} pts
              </span>
            </div>
            <div>
              <span className="text-muted">Time to hit:</span>{" "}
              <span className="font-mono text-card-foreground">
                ~{Math.ceil(rec.months_to_hit)} mo
              </span>
            </div>
            <div>
              <span className="text-muted">Score:</span>{" "}
              <span className="font-mono text-card-foreground">
                {rec.score.toLocaleString()}
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
    good: <CheckCircle className="w-5 h-5 text-emerald-500" />,
    underperforming: <AlertTriangle className="w-5 h-5 text-amber-500" />,
    costing_money: <AlertTriangle className="w-5 h-5 text-red-500" />,
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
                className={`font-mono font-medium ${card.net_value >= 0 ? "text-emerald-500" : "text-red-500"}`}
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
                      <span className="text-emerald-500 font-mono">
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

export default function RecommendationsPage() {
  const [tab, setTab] = useState<"next-card" | "portfolio">("next-card");
  const queryClient = useQueryClient();

  const refreshMutation = useMutation({
    mutationFn: refreshRecommendations,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">
            Recommendations
          </h1>
          <p className="text-sm text-muted mt-1">
            Personalized credit card advice based on your spending
          </p>
        </div>
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
      </div>

      {tab === "next-card" ? <NextCardTab /> : <PortfolioTab />}
    </div>
  );
}

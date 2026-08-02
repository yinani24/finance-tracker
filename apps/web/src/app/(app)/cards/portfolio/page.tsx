"use client";

import { useQuery } from "@tanstack/react-query";
import { getPortfolioAnalysis } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Lightbulb, AlertTriangle, CheckCircle } from "lucide-react";
import { RefreshRecommendationsButton } from "@/components/refresh-recommendations-button";

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
  const assignments = data?.category_assignments ?? [];

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
    underperforming: <AlertTriangle className="w-5 h-5 text-warning" />,
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

      {assignments.length > 0 && (
        <div className="bg-card rounded-xl border border-border p-6">
          <h3 className="font-semibold text-card-foreground mb-1">
            Which card to use where
          </h3>
          <p className="text-xs text-muted mb-4">
            The best card you already hold for each category you spend in.
          </p>
          <div className="space-y-3">
            {assignments.map((a) => (
              <div
                key={a.category}
                className="flex items-start justify-between gap-3 text-sm"
              >
                <div>
                  <span className="text-card-foreground font-medium">
                    {formatCategoryName(a.category)}
                  </span>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {a.rationale}
                  </p>
                </div>
                <div className="text-right shrink-0">
                  <span className="text-card-foreground">
                    {a.best_card.name}
                  </span>
                  {a.best_card.issuer && (
                    <span className="text-muted ml-2 text-xs">
                      {a.best_card.issuer}
                    </span>
                  )}
                  <div className="font-mono text-xs text-success mt-0.5">
                    {a.rate.toLocaleString(undefined, {
                      maximumFractionDigits: 2,
                    })}
                    %
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function PortfolioPage() {
  return (
    <div>
      <RefreshRecommendationsButton />
      <PortfolioTab />
    </div>
  );
}

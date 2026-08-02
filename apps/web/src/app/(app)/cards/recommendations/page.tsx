"use client";

import { useQuery } from "@tanstack/react-query";
import { getNextCardRecommendations } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Lightbulb, ExternalLink } from "lucide-react";
import { RefreshRecommendationsButton } from "@/components/refresh-recommendations-button";

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
          className="card-interactive bg-card rounded-xl border border-border p-6"
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
                className="text-muted-foreground hover:text-card-foreground motion-base"
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

export default function RecommendationsPage() {
  return (
    <div>
      <RefreshRecommendationsButton />
      <NextCardTab />
    </div>
  );
}

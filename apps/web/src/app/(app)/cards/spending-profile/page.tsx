"use client";

import { useQuery } from "@tanstack/react-query";
import { getSpendingProfile } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { PieChart, Utensils, Store } from "lucide-react";
import { RefreshRecommendationsButton } from "@/components/refresh-recommendations-button";

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
            <Utensils className="w-5 h-5 text-warning" />
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
              <div className="h-2 rounded-full bg-accent overflow-hidden">
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

export default function SpendingProfilePage() {
  return (
    <div>
      <RefreshRecommendationsButton />
      <SpendingTab />
    </div>
  );
}

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getPlaidItems,
  syncPlaidItem,
  deletePlaidItem,
  getPreferences,
  updatePreferences,
} from "@/lib/api";
import { PlaidLinkButton } from "@/components/plaid-link-button";
import { formatDate } from "@/lib/format";
import { RefreshCw, Trash2, Building2, Globe, Gauge, Sun, Moon, Monitor } from "lucide-react";
import { useState, useEffect } from "react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import type { UserPreference } from "@/lib/types";
import type { SyncResult } from "@/lib/types";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [syncResult, setSyncResult] = useState<SyncResult | null>(null);
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [browserTimezone, setBrowserTimezone] = useState("America/New_York");

  useEffect(() => {
    setMounted(true);
    setBrowserTimezone(Intl.DateTimeFormat().resolvedOptions().timeZone);
  }, []);

  const { data: plaidItems = [] } = useQuery({
    queryKey: ["plaid-items"],
    queryFn: getPlaidItems,
  });

  const { data: prefs } = useQuery({
    queryKey: ["preferences"],
    queryFn: getPreferences,
  });

  const syncMutation = useMutation({
    mutationFn: syncPlaidItem,
    onSuccess: (result) => {
      setSyncResult(result);
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deletePlaidItem,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plaid-items"] });
    },
  });

  const prefsMutation = useMutation({
    mutationFn: (data: Partial<UserPreference>) =>
      updatePreferences(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["preferences"] });
    },
  });


  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Settings
        </h1>
        <p className="text-sm text-muted mt-1">
          Manage connections and preferences
        </p>
      </div>

      <section className="bg-card rounded-xl border border-border p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-card-foreground">
            Connected Banks
          </h2>
          <PlaidLinkButton />
        </div>

        {plaidItems.length === 0 ? (
          <p className="text-muted-foreground text-sm leading-relaxed">
            No bank accounts connected. Click &quot;Connect Bank Account&quot;
            to get started with Plaid.
          </p>
        ) : (
          <div className="space-y-3">
            {plaidItems.map((item) => (
              <div
                key={item.id}
                className="flex items-center justify-between py-3 border-b border-border last:border-0"
              >
                <div className="flex items-center gap-3">
                  <Building2 className="w-5 h-5 text-muted-foreground" />
                  <div>
                    <div className="text-sm font-medium text-card-foreground">
                      {item.institution_name || item.item_id}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Status: {item.status} &middot; Linked{" "}
                      {formatDate(item.created_at)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => syncMutation.mutate(item.id)}
                    disabled={syncMutation.isPending}
                    className="flex items-center gap-1.5 text-sm text-accent-foreground hover:text-accent-foreground/80 px-3 py-1.5 rounded-lg hover:bg-accent motion-base disabled:opacity-50"
                  >
                    <RefreshCw
                      className={cn(
                        "w-3.5 h-3.5",
                        syncMutation.isPending && "animate-spin"
                      )}
                    />
                    Sync
                  </button>
                  <button
                    onClick={() => {
                      if (confirm("Remove this bank connection?")) {
                        deleteMutation.mutate(item.id);
                      }
                    }}
                    disabled={deleteMutation.isPending}
                    className="flex items-center gap-1.5 text-sm text-destructive px-3 py-1.5 rounded-lg hover:bg-destructive/10 motion-base disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {syncResult && (
          <div className="mt-4 bg-success/10 border border-success/20 rounded-lg p-4 text-sm text-success">
            Sync complete:{" "}
            <span className="font-mono tabular-nums">
              {syncResult.transactions_added}
            </span>{" "}
            added,{" "}
            <span className="font-mono tabular-nums">
              {syncResult.transactions_modified}
            </span>{" "}
            modified,{" "}
            <span className="font-mono tabular-nums">
              {syncResult.transactions_removed}
            </span>{" "}
            removed,{" "}
            <span className="font-mono tabular-nums">
              {syncResult.accounts_synced}
            </span>{" "}
            accounts synced.
          </div>
        )}
      </section>

      {/* Credit standing — feeds the approval-odds estimate so recommendations
          rank by expected value rather than headline value. Entirely optional:
          leaving it unset ranks on value alone, exactly as before. */}
      <section className="bg-card rounded-xl border border-border p-6">
        <div className="flex items-center gap-3 mb-1">
          <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
            <Gauge className="w-4 h-4 text-accent-foreground" />
          </div>
          <div>
            <div className="text-sm font-medium text-card-foreground">
              Credit standing
            </div>
            <div className="text-xs text-muted-foreground">
              Optional. Used to estimate approval odds, so we stop recommending
              cards you are unlikely to get.
            </div>
          </div>
        </div>

        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted">
              Credit score range
            </label>
            <select
              value={prefs?.credit_score_band ?? ""}
              onChange={(e) =>
                prefsMutation.mutate({
                  credit_score_band: e.target.value || null,
                })
              }
              className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
            >
              <option value="">Prefer not to say</option>
              <option value="excellent">Excellent (740+)</option>
              <option value="good">Good (670–739)</option>
              <option value="fair">Fair (580–669)</option>
              <option value="poor">Poor (below 580)</option>
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium text-muted">
              Cards opened in the last 24 months
            </label>
            <input
              type="number"
              min={0}
              max={20}
              value={prefs?.recent_card_applications ?? ""}
              placeholder="e.g. 2"
              onChange={(e) =>
                prefsMutation.mutate({
                  recent_card_applications: e.target.value
                    ? Number(e.target.value)
                    : null,
                })
              }
              className="w-full rounded-lg border border-input bg-background px-3 py-2 font-mono text-sm text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Some issuers decline applicants past a threshold (Chase at 5).
            </p>
          </div>
        </div>
      </section>

      <section className="bg-card rounded-xl border border-border p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center">
              <Globe className="w-4 h-4 text-accent-foreground" />
            </div>
            <div>
              <div className="text-sm font-medium text-card-foreground">
                Timezone
              </div>
              <div className="text-xs text-muted-foreground">
                {browserTimezone} &middot; detected from browser
              </div>
            </div>
          </div>
          {mounted && (
            <div className="flex items-center gap-0.5 bg-background rounded-lg p-0.5">
              {(["light", "dark", "system"] as const).map((opt) => {
                const Icon =
                  opt === "light" ? Sun : opt === "dark" ? Moon : Monitor;
                return (
                  <button
                    key={opt}
                    onClick={() => {
                      setTheme(opt);
                      prefsMutation.mutate({ theme: opt });
                    }}
                    className={cn(
                      // Flat like the rest of the system: the active pill is
                      // marked by a border, not a shadow, so it still reads on
                      // the dark canvas where shadows are invisible.
                      "p-1.5 rounded-md border motion-base",
                      theme === opt
                        ? "bg-card text-card-foreground border-border"
                        : "border-transparent text-muted-foreground hover:text-card-foreground"
                    )}
                    title={opt.charAt(0).toUpperCase() + opt.slice(1)}
                  >
                    <Icon className="w-4 h-4" />
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

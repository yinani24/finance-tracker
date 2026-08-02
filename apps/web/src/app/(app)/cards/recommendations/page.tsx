"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Lightbulb, ExternalLink, Loader2 } from "lucide-react";
import { postStatelessRecommendations } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { useSession } from "@/lib/session/session-context";
import { summarize, categoryTotals } from "@/lib/session/derive";
import { StatementDropzone } from "@/components/statement-dropzone";

/** The dataset stores issuers and networks as enums (AMERICAN_EXPRESS). */
function pretty(value: string | null | undefined): string {
  if (!value) return "";
  return value
    .split(/[_\s]+/)
    .map((w) => w.charAt(0) + w.slice(1).toLowerCase())
    .join(" ");
}

/**
 * What to get next, ranked against the spending in this session.
 *
 * This read the DB-backed endpoint, which ranks from stored transactions the
 * client-only flow never writes — so it always rendered "no recommendations
 * yet" no matter how many statements had been dropped. It now posts the
 * locally-derived profile instead.
 */
export default function RecommendationsPage() {
  const { session, ready, setCredit } = useSession();

  const summary = useMemo(() => summarize(session), [session]);
  const cats = useMemo(
    () => categoryTotals(session.transactions),
    [session.transactions]
  );

  const hasData = ready && session.transactions.length > 0;

  const { data, isLoading } = useQuery({
    queryKey: [
      "recommendations",
      "stateless",
      Math.round(summary.monthlySpend),
      cats.map((c) => `${c.category}:${Math.round(c.total)}`).join(","),
      session.credit.scoreBand,
      session.heldCards.map((c) => c.name).join(","),
    ],
    enabled: hasData,
    queryFn: () =>
      postStatelessRecommendations({
        avg_monthly_spend: summary.monthlySpend,
        category_breakdown: Object.fromEntries(
          cats.map((c) => [c.category, c.total / summary.months])
        ),
        held_cards: session.heldCards.map((c) => ({
          name: c.name,
          issuer: c.issuer,
        })),
        credit_score_band: session.credit.scoreBand ?? null,
        recent_card_applications: session.credit.recentApplications ?? null,
        max_results: 10,
      }),
  });

  if (ready && !hasData) {
    return (
      <div className="max-w-3xl">
        <p className="text-sm text-muted mb-6">
          Drop a statement and these rank themselves against what you actually
          spend.
        </p>
        <StatementDropzone />
      </div>
    );
  }

  const recs = data?.recommendations ?? [];

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <p className="text-sm text-muted">
          Ranked for {formatCurrency(summary.monthlySpend)} a month
          {summary.topCategory ? `, mostly ${summary.topCategory.category}` : ""}
          {session.heldCards.length > 0
            ? ` · excludes the ${session.heldCards.length} card${session.heldCards.length === 1 ? "" : "s"} you hold`
            : ""}
        </p>

        {/* Credit standing belongs next to what it changes: it re-ranks these
            by expected value rather than headline value. Optional. */}
        <label className="flex items-center gap-2 text-xs text-muted">
          Credit
          <select
            value={session.credit.scoreBand ?? ""}
            onChange={(e) =>
              setCredit({
                scoreBand: (e.target.value || undefined) as
                  | "excellent"
                  | "good"
                  | "fair"
                  | "poor"
                  | undefined,
              })
            }
            className="border border-input bg-background px-2 py-1 text-xs text-foreground motion-base focus:border-ring focus:outline-none focus:ring-2 focus:ring-ring/40"
          >
            <option value="">Not set</option>
            <option value="excellent">Excellent (740+)</option>
            <option value="good">Good (670–739)</option>
            <option value="fair">Fair (580–669)</option>
            <option value="poor">Poor (&lt;580)</option>
          </select>
        </label>
      </div>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          Ranking cards against your spending…
        </div>
      )}

      {!isLoading && recs.length === 0 && (
        <div className="border border-border py-12 text-center text-muted">
          <Lightbulb className="mx-auto mb-3 h-8 w-8 opacity-50" />
          <p className="text-sm">
            No card beat the ones you already hold at this spending level.
          </p>
        </div>
      )}

      <div className="space-y-3">
        {recs.map((rec, i) => (
          <div key={rec.card.cardId} className="card-interactive border border-border p-6">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div className="flex min-w-0 items-baseline gap-3">
                <span className="font-mono text-sm text-muted">{i + 1}.</span>
                <div className="min-w-0">
                  <h3 className="font-semibold text-card-foreground">
                    {rec.card.name}
                  </h3>
                  <p className="text-sm text-muted">
                    {pretty(rec.card.issuer)}
                    {/* Several issuers are their own network, so printing both
                        renders "American Express · American Express". */}
                    {rec.card.network &&
                    rec.card.network !== rec.card.issuer
                      ? ` · ${pretty(rec.card.network)}`
                      : ""}
                    {rec.card.annualFee > 0
                      ? ` · ${formatCurrency(rec.card.annualFee)}/yr${
                          rec.card.isAnnualFeeWaived ? ", waived year one" : ""
                        }`
                      : " · no annual fee"}
                  </p>
                </div>
              </div>
              <div className="flex flex-shrink-0 items-center gap-3">
                <div className="text-right">
                  <div className="font-mono text-lg tabular-nums text-success">
                    ~${Math.round(rec.score).toLocaleString()}
                  </div>
                  <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                    first-year value
                  </div>
                </div>
                {rec.card.url && (
                  <a
                    href={rec.card.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-muted-foreground hover:text-card-foreground motion-base"
                    aria-label={`Open ${rec.card.name}`}
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                )}
              </div>
            </div>

            <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
              <span>
                {/* bonus_value is the offer's dollar value, not a point count —
                    the engine already converts points at the configured rate. */}
                <span className="text-muted">Bonus worth</span>{" "}
                <span className="font-mono tabular-nums text-card-foreground">
                  {formatCurrency(rec.bonus_value)}
                </span>
              </span>
              <span>
                <span className="text-muted">Time to hit</span>{" "}
                <span className="font-mono tabular-nums text-card-foreground">
                  ~{Math.ceil(rec.months_to_hit)} mo
                </span>
              </span>
              {rec.approval_label && (
                <span title={rec.approval_reason ?? undefined}>
                  <span className="text-muted">Approval odds</span>{" "}
                  <span className="mono-chip capitalize">{rec.approval_label}</span>
                </span>
              )}
            </div>

            {rec.explanation && (
              <p className="mt-3 text-sm text-muted-foreground">{rec.explanation}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

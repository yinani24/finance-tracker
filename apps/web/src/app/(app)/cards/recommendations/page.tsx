"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Lightbulb, ExternalLink, Loader2 } from "lucide-react";
import {
  postStatelessRecommendations,
  postStatelessCombination,
  hasApi,
  type StatelessProfileRequest,
} from "@/lib/api";
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

  // One profile, two recommenders: "what to get next" (single best cards) and
  // "the optimal set" (combination) rank against the exact same locally-derived
  // spending. Factoring it here keeps the two calls from drifting apart.
  const profile = useMemo<StatelessProfileRequest>(
    () => ({
      avg_monthly_spend: summary.monthlySpend,
      category_breakdown: Object.fromEntries(
        cats.map((c) => [c.category, c.total / summary.months])
      ),
      held_cards: session.heldCards.map((c) => ({
        // The dataset is keyed on the product name, not the display label.
        name: c.productName ?? c.name,
        issuer: c.issuer,
      })),
      credit_score_band: session.credit.scoreBand ?? null,
      recent_card_applications: session.credit.recentApplications ?? null,
      max_results: 10,
    }),
    [
      summary.monthlySpend,
      summary.months,
      cats,
      session.heldCards,
      session.credit.scoreBand,
      session.credit.recentApplications,
    ]
  );

  // The two queries share the same discriminators so they invalidate together.
  const queryInputs = [
    Math.round(summary.monthlySpend),
    cats.map((c) => `${c.category}:${Math.round(c.total)}`).join(","),
    session.credit.scoreBand,
    session.heldCards.map((c) => c.name).join(","),
  ];

  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", "stateless", ...queryInputs],
    enabled: hasData && hasApi,
    queryFn: () => postStatelessRecommendations(profile),
  });

  const { data: combo } = useQuery({
    queryKey: ["combination", "stateless", ...queryInputs],
    enabled: hasData && hasApi,
    queryFn: () => postStatelessCombination(profile),
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

      {/* The optimal SET of cards (held + new) — the combination recommender,
          PRODUCT.md Decision #1. Distinct from the ranked-singles list below:
          this answers "which cards, together, extract the most first-year
          value," then routes each spending category to whichever card in that
          combined wallet earns most on it. Every figure below is USD; `rate`
          is already a percent-equivalent, so it renders as-is. */}
      {hasApi && combo && (
        <section className="mb-8 border border-border p-6">
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            The optimal set of cards
          </h2>

          {combo.recommended_new_cards.length === 0 ? (
            <p className="mt-2 text-sm text-muted">
              Your current wallet is already optimal for this spending — no card
              worth adding.
            </p>
          ) : (
            <>
              <p className="mt-2 text-sm text-muted">
                Adding{" "}
                {combo.recommended_new_cards.length === 1
                  ? "this card"
                  : `these ${combo.recommended_new_cards.length} cards`}{" "}
                lifts your first-year value from{" "}
                <span className="font-mono tabular-nums text-card-foreground">
                  {formatCurrency(combo.baseline_first_year_value)}
                </span>{" "}
                to{" "}
                <span className="font-mono tabular-nums text-success">
                  {formatCurrency(combo.projected_first_year_value)}
                </span>{" "}
                <span className="text-success">
                  (+
                  {formatCurrency(
                    combo.projected_first_year_value -
                      combo.baseline_first_year_value
                  )}
                  )
                </span>
                .
              </p>

              <div className="mt-4 space-y-3">
                {combo.recommended_new_cards.map((c) => (
                  <div
                    key={`${c.name}:${c.issuer}`}
                    className="border border-border p-4"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0">
                        <h3 className="font-semibold text-card-foreground">
                          {c.name}
                        </h3>
                        <p className="text-sm text-muted">{pretty(c.issuer)}</p>
                      </div>
                      <div className="flex-shrink-0 text-right">
                        <div className="font-mono tabular-nums text-success">
                          +{formatCurrency(c.marginal_value)}
                        </div>
                        <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                          first-year value
                        </div>
                      </div>
                    </div>
                    {c.categories_won.length > 0 && (
                      <p className="mt-2 text-xs text-muted">
                        Wins{" "}
                        <span className="text-card-foreground">
                          {c.categories_won.join(", ")}
                        </span>
                      </p>
                    )}
                    {c.rationale && (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {c.rationale}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}

          {combo.per_category_routing.length > 0 && (
            <div className="mt-5">
              <h3 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Which card to use, by category
              </h3>
              <ul className="mt-2 divide-y divide-border border border-border">
                {combo.per_category_routing.map((r) => (
                  <li
                    key={r.category}
                    className="flex items-center justify-between gap-4 px-4 py-2 text-sm"
                  >
                    <span className="capitalize text-muted">{r.category}</span>
                    <span className="flex items-center gap-2 text-right">
                      <span className="text-card-foreground">
                        {r.card.name}
                      </span>
                      {r.is_new && (
                        <span className="mono-chip text-[10px] uppercase">
                          new
                        </span>
                      )}
                      <span className="font-mono tabular-nums text-muted">
                        {r.rate.toFixed(1)}%
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="h-4 w-4 animate-spin" />
          Ranking cards against your spending…
        </div>
      )}

      {!hasApi && (
        <div className="border border-border py-12 text-center text-muted">
          <Lightbulb className="mx-auto mb-3 h-8 w-8 opacity-50" />
          <p className="mx-auto max-w-md text-sm">
            Card ranking needs the card dataset, which is served by the API.
            Set <code className="font-mono text-xs">NEXT_PUBLIC_API_URL</code>{" "}
            to a running instance to enable it. Everything else on this site —
            parsing, spending, subscriptions, income — runs in your browser and
            works without it.
          </p>
        </div>
      )}

      {hasApi && !isLoading && recs.length === 0 && (
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

"use client";

import { useEffect, useState } from "react";
import { useQuery, keepPreviousData } from "@tanstack/react-query";
import { searchCardBonuses, getCardBonusIssuers } from "@/lib/api";
import type { CardBonus, CardBonusOffer } from "@/lib/types";
import { formatCurrency } from "@/lib/format";
import { Search, CreditCard, ExternalLink, Gift } from "lucide-react";

const PAGE_SIZE = 24;

// Common networks in the public dataset. There is no `/networks` endpoint, so
// this mirrors the fixed set used by the "Add Card" form.
const NETWORKS = ["visa", "mastercard", "amex", "discover"] as const;

const FEE_OPTIONS = [
  { label: "Any annual fee", value: "" },
  { label: "No annual fee", value: "0" },
  { label: "Up to $95", value: "95" },
  { label: "Up to $250", value: "250" },
  { label: "Up to $550", value: "550" },
] as const;

// Pick the offer with the highest total bonus value. `amount` is a list of
// award buckets ({amount, currency}); we rank by their sum.
function bestOffer(card: CardBonus): CardBonusOffer | null {
  if (!card.offers?.length) return null;
  const value = (o: CardBonusOffer) =>
    o.amount.reduce((sum, a) => sum + (a.amount || 0), 0);
  return [...card.offers].sort((a, b) => value(b) - value(a))[0];
}

function formatBonus(offer: CardBonusOffer, cardCurrency: string): string {
  return offer.amount
    .map((a) => {
      const currency = a.currency || cardCurrency;
      return currency === "USD"
        ? formatCurrency(a.amount, "USD")
        : `${a.amount.toLocaleString()} ${currency}`;
    })
    .join(" + ");
}

function formatRequirement(offer: CardBonusOffer): string {
  const spend = formatCurrency(offer.spend, "USD");
  const months = Math.round(offer.days / 30);
  const window =
    months >= 1 ? `${months} month${months > 1 ? "s" : ""}` : `${offer.days} days`;
  return `Spend ${spend} in ${window}`;
}

export default function ExplorePage() {
  const [searchInput, setSearchInput] = useState("");
  const [q, setQ] = useState("");
  const [issuer, setIssuer] = useState("");
  const [network, setNetwork] = useState("");
  const [maxFee, setMaxFee] = useState("");
  const [business, setBusiness] = useState(""); // "" | "false" | "true"
  const [page, setPage] = useState(0);

  // Debounce the free-text search so we issue one request after typing settles.
  useEffect(() => {
    const t = setTimeout(() => {
      setQ(searchInput.trim());
      setPage(0);
    }, 300);
    return () => clearTimeout(t);
  }, [searchInput]);

  const { data: issuers = [] } = useQuery({
    queryKey: ["card-bonus-issuers"],
    queryFn: getCardBonusIssuers,
  });

  const { data, isLoading, isError } = useQuery({
    queryKey: ["card-bonuses", q, issuer, network, maxFee, business, page],
    queryFn: () =>
      searchCardBonuses({
        q: q || undefined,
        issuer: issuer || undefined,
        network: network || undefined,
        max_annual_fee: maxFee ? Number(maxFee) : undefined,
        is_business: business === "" ? undefined : business === "true",
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      }),
    placeholderData: keepPreviousData,
  });

  const cards = data?.results ?? [];
  const total = data?.total ?? 0;
  const pageCount = Math.ceil(total / PAGE_SIZE);
  const from = total === 0 ? 0 : page * PAGE_SIZE + 1;
  const to = Math.min((page + 1) * PAGE_SIZE, total);

  const selectClass =
    "border border-input bg-background text-foreground rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors";

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Explore cards
        </h1>
        <p className="text-sm text-muted mt-1">
          {isLoading ? (
            <span className="inline-block h-4 w-40 bg-muted rounded animate-pulse align-middle" />
          ) : (
            <>
              Browse{" "}
              <span className="font-mono tabular-nums">{total}</span> cards and
              their current sign-up offers
            </>
          )}
        </p>
      </div>

      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search cards..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            className="w-full border border-input bg-background text-foreground rounded-lg pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
          />
        </div>
        <select
          value={issuer}
          onChange={(e) => {
            setIssuer(e.target.value);
            setPage(0);
          }}
          className={selectClass}
          aria-label="Filter by issuer"
        >
          <option value="">All issuers</option>
          {issuers.map((i) => (
            <option key={i} value={i}>
              {i}
            </option>
          ))}
        </select>
        <select
          value={network}
          onChange={(e) => {
            setNetwork(e.target.value);
            setPage(0);
          }}
          className={selectClass}
          aria-label="Filter by network"
        >
          <option value="">All networks</option>
          {NETWORKS.map((n) => (
            <option key={n} value={n}>
              {n.charAt(0).toUpperCase() + n.slice(1)}
            </option>
          ))}
        </select>
        <select
          value={maxFee}
          onChange={(e) => {
            setMaxFee(e.target.value);
            setPage(0);
          }}
          className={selectClass}
          aria-label="Filter by annual fee"
        >
          {FEE_OPTIONS.map((f) => (
            <option key={f.label} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
        <select
          value={business}
          onChange={(e) => {
            setBusiness(e.target.value);
            setPage(0);
          }}
          className={selectClass}
          aria-label="Filter by card type"
        >
          <option value="">Personal &amp; business</option>
          <option value="false">Personal</option>
          <option value="true">Business</option>
        </select>
      </div>

      {isError ? (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-500">
          Couldn&apos;t load cards. Please try again.
        </div>
      ) : isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-40 bg-card rounded-xl border border-border animate-pulse"
            />
          ))}
        </div>
      ) : cards.length === 0 ? (
        <div className="text-center py-16 text-muted">
          <CreditCard className="w-8 h-8 mx-auto mb-3 opacity-50" />
          <p>No cards match your filters.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {cards.map((card) => {
              const offer = bestOffer(card);
              return (
                <div
                  key={card.cardId}
                  className="flex flex-col bg-card rounded-xl border border-border p-5"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="text-sm font-semibold text-card-foreground truncate">
                        {card.name}
                      </h2>
                      <p className="text-xs text-muted mt-0.5">
                        {card.issuer}
                        {card.network ? ` · ${card.network}` : ""}
                        {card.isBusiness ? " · Business" : ""}
                      </p>
                    </div>
                    {card.url && (
                      <a
                        href={card.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
                        aria-label={`Open ${card.name} details`}
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                  </div>

                  <div className="mt-3 text-xs text-muted">
                    {card.annualFee > 0
                      ? `${formatCurrency(card.annualFee, "USD")} annual fee${
                          card.isAnnualFeeWaived ? " (waived first year)" : ""
                        }`
                      : "No annual fee"}
                  </div>

                  <div className="mt-auto pt-4">
                    {offer ? (
                      <div className="rounded-lg bg-background border border-border px-3 py-2.5">
                        <div className="flex items-center gap-1.5 text-sm font-medium text-card-foreground">
                          <Gift className="w-3.5 h-3.5 text-muted-foreground" />
                          {formatBonus(offer, card.currency)}
                        </div>
                        <div className="text-xs text-muted mt-1">
                          {formatRequirement(offer)}
                        </div>
                      </div>
                    ) : (
                      <div className="text-xs text-muted">
                        No current sign-up offer
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>

          {pageCount > 1 && (
            <div className="flex items-center justify-between mt-6">
              <p className="text-xs text-muted">
                Showing{" "}
                <span className="font-mono tabular-nums">
                  {from}–{to}
                </span>{" "}
                of <span className="font-mono tabular-nums">{total}</span>
              </p>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(0, p - 1))}
                  disabled={page === 0}
                  className="border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-muted/10 transition-colors"
                >
                  Previous
                </button>
                <button
                  onClick={() => setPage((p) => (to < total ? p + 1 : p))}
                  disabled={to >= total}
                  className="border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed hover:bg-muted/10 transition-colors"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

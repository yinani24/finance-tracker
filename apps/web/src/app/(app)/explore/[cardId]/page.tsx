"use client";

import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getCardBonus, getCards, createCard } from "@/lib/api";
import type { CardBonus, CardBonusOffer } from "@/lib/types";
import { formatCurrency } from "@/lib/format";
import {
  ArrowLeft,
  ExternalLink,
  Gift,
  CreditCard,
  Sparkles,
  Plus,
  Check,
} from "lucide-react";

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

// Rank offers by total bonus value (highest first) so the best offer leads.
function sortedOffers(card: CardBonus): CardBonusOffer[] {
  if (!card.offers?.length) return [];
  const value = (o: CardBonusOffer) =>
    o.amount.reduce((sum, a) => sum + (a.amount || 0), 0);
  return [...card.offers].sort((a, b) => value(b) - value(a));
}

function is404(error: unknown): boolean {
  return error instanceof Error && error.message.includes("API 404");
}

// Moves a catalog card into the user's tracked wallet via POST /cards. Stores
// `name` and `issuer` verbatim from the dataset so the held card matches its
// catalog entry under the recommendation engine's `name.lower()|issuer.upper()`
// key (see apps/api/app/services/card_recommendation.py) — that match is what
// lets the portfolio analysis value the card, so this is more than a shortcut.
function AddToWalletButton({ card }: { card: CardBonus }) {
  const queryClient = useQueryClient();

  // Used only to detect duplicates. If it fails to load (e.g. no session), we
  // fall back to showing the add button rather than blocking the action.
  const { data: cards } = useQuery({
    queryKey: ["cards"],
    queryFn: getCards,
  });

  const alreadyInWallet = Boolean(
    cards?.some((c) => c.name.toLowerCase() === card.name.toLowerCase())
  );

  const mutation = useMutation({
    mutationFn: () =>
      createCard({
        name: card.name,
        issuer: card.issuer,
        network: card.network,
        annual_fee: card.annualFee,
      }),
    onSuccess: () => {
      // Adding a card changes portfolio recommendations, so refresh both — the
      // same invalidation the Cards page uses on manual add/edit/delete.
      queryClient.invalidateQueries({ queryKey: ["cards"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
    onError: () => {},
  });

  if (alreadyInWallet) {
    return (
      <span className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-muted">
        <Check className="w-4 h-4" />
        In your wallet
      </span>
    );
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="inline-flex items-center gap-1.5 rounded-lg bg-foreground px-4 py-2.5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-50 transition-opacity active:translate-y-px"
      >
        <Plus className="w-4 h-4" />
        {mutation.isPending ? "Adding…" : "Add to my wallet"}
      </button>
      {mutation.isError && (
        <span className="text-xs text-red-500">
          Couldn&apos;t add. Try again.
        </span>
      )}
    </div>
  );
}

const backLink = (
  <Link
    href="/explore"
    className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
  >
    <ArrowLeft className="w-4 h-4" />
    Back to Explore
  </Link>
);

export default function CardDetailPage() {
  const params = useParams();
  const cardId = Array.isArray(params.cardId) ? params.cardId[0] : params.cardId;

  const { data: card, isLoading, isError, error } = useQuery({
    queryKey: ["card-bonus", cardId],
    queryFn: () => getCardBonus(cardId as string),
    enabled: Boolean(cardId),
    retry: (count, err) => !is404(err) && count < 2,
  });

  if (isLoading) {
    return (
      <div className="p-8 max-w-3xl mx-auto">
        {backLink}
        <div className="mt-6 h-8 w-64 bg-muted rounded animate-pulse" />
        <div className="mt-4 h-40 bg-card rounded-xl border border-border animate-pulse" />
      </div>
    );
  }

  if (isError || !card) {
    const notFound = is404(error);
    return (
      <div className="p-8 max-w-3xl mx-auto">
        {backLink}
        <div className="mt-8 text-center py-16 text-muted">
          <CreditCard className="w-8 h-8 mx-auto mb-3 opacity-50" />
          <p className="font-medium text-card-foreground">
            {notFound ? "Card not found" : "Couldn't load this card"}
          </p>
          <p className="text-sm mt-1">
            {notFound
              ? "This card isn't in the catalog. It may have been renamed or removed."
              : "Please try again."}
          </p>
        </div>
      </div>
    );
  }

  const offers = sortedOffers(card);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      {backLink}

      <div className="mt-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">{card.name}</h1>
          <p className="text-sm text-muted mt-1">
            {card.issuer}
            {card.network ? ` · ${card.network}` : ""}
            {card.isBusiness ? " · Business" : ""}
          </p>
        </div>
        <AddToWalletButton card={card} />
      </div>

      {/* Key facts */}
      <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="rounded-xl bg-card border border-border p-5">
          <p className="text-xs text-muted uppercase tracking-wide">Annual fee</p>
          <p className="mt-1 text-lg font-semibold text-card-foreground">
            {card.annualFee > 0
              ? formatCurrency(card.annualFee, "USD")
              : "No annual fee"}
          </p>
          {card.annualFee > 0 && card.isAnnualFeeWaived && (
            <p className="text-xs text-muted mt-0.5">Waived the first year</p>
          )}
        </div>
        <div className="rounded-xl bg-card border border-border p-5">
          <p className="text-xs text-muted uppercase tracking-wide">
            Base earn rate
          </p>
          <p className="mt-1 text-lg font-semibold text-card-foreground">
            {card.universalCashbackPercent > 0
              ? `${card.universalCashbackPercent}% on all purchases`
              : "—"}
          </p>
        </div>
      </div>

      {/* Sign-up offers */}
      <div className="mt-8">
        <h2 className="text-sm font-semibold text-card-foreground flex items-center gap-1.5">
          <Gift className="w-4 h-4 text-muted-foreground" />
          Sign-up offers
        </h2>
        {offers.length === 0 ? (
          <p className="text-sm text-muted mt-3">No current sign-up offer.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {offers.map((offer, i) => (
              <li
                key={i}
                className="rounded-lg bg-card border border-border px-4 py-3"
              >
                <p className="text-sm font-medium text-card-foreground">
                  {formatBonus(offer, card.currency)}
                </p>
                <p className="text-xs text-muted mt-1">
                  {formatRequirement(offer)}
                </p>
                {offer.url && (
                  <a
                    href={offer.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors mt-2"
                  >
                    Offer terms
                    <ExternalLink className="w-3 h-3" />
                  </a>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Credits / perks */}
      {card.credits?.length > 0 && (
        <div className="mt-8">
          <h2 className="text-sm font-semibold text-card-foreground flex items-center gap-1.5">
            <Sparkles className="w-4 h-4 text-muted-foreground" />
            Credits &amp; perks
          </h2>
          <ul className="mt-3 space-y-2">
            {card.credits.map((credit, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-3 text-sm border-b border-border/60 pb-2 last:border-0"
              >
                <span className="text-card-foreground">{credit.description}</span>
                {credit.value > 0 && (
                  <span className="text-muted shrink-0 font-mono tabular-nums">
                    {formatCurrency(credit.value, credit.currency || "USD")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Apply / official link */}
      {card.url && (
        <div className="mt-8">
          <a
            href={card.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-4 py-2.5 text-sm font-medium text-card-foreground hover:bg-background transition-colors"
          >
            Official card page
            <ExternalLink className="w-4 h-4" />
          </a>
        </div>
      )}
    </div>
  );
}

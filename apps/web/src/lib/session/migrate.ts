import { normalizeMerchant } from "../statement/normalize-merchant";
import type { HeldCard, SessionState } from "./types";

/**
 * Fold cards that are really the same account into one.
 *
 * Before card identity was keyed on the account number, each statement for the
 * same card created a new entry — successive statements differ in credit limit
 * and, when the account-number line fails to parse, in the display label too.
 * A session written then holds one card three times, and every utilization and
 * portfolio figure counts it three times over.
 *
 * The survivor keeps the newest statement's limit and balance, and the
 * transactions of the entries it absorbs are repointed to it.
 */
function dedupeCards(session: SessionState): SessionState {
  const identity = (c: HeldCard) =>
    c.last4
      ? `l4:${c.last4}`
      : c.productName
        ? `p:${c.productName.toLowerCase()}|${(c.issuer ?? "").toLowerCase()}`
        : `n:${c.name.toLowerCase()}`;

  const groups = new Map<string, HeldCard[]>();
  for (const card of session.heldCards) {
    const key = identity(card);
    groups.set(key, [...(groups.get(key) ?? []), card]);
  }
  if (groups.size === session.heldCards.length) return session;

  const remap = new Map<string, string>();
  const merged: HeldCard[] = [];
  for (const group of groups.values()) {
    // Newest statement wins; entries with no period fall to the back.
    const ordered = [...group].sort((a, b) =>
      (b.statementThrough ?? "").localeCompare(a.statementThrough ?? "")
    );
    const survivor = ordered[0];
    const winner: HeldCard = {
      ...survivor,
      // Fill any gap the newest statement left from the others.
      creditLimit:
        survivor.creditLimit ?? ordered.find((c) => c.creditLimit)?.creditLimit,
      currentBalance:
        survivor.currentBalance ??
        ordered.find((c) => c.currentBalance != null)?.currentBalance,
      last4: survivor.last4 ?? ordered.find((c) => c.last4)?.last4,
      productName:
        survivor.productName ?? ordered.find((c) => c.productName)?.productName,
    };
    for (const card of group) remap.set(card.id, winner.id);
    merged.push(winner);
  }

  return {
    ...session,
    heldCards: merged,
    transactions: session.transactions.map((t) =>
      t.sourceId && remap.get(t.sourceId) !== t.sourceId
        ? { ...t, sourceId: remap.get(t.sourceId) ?? t.sourceId }
        : t
    ),
  };
}

/**
 * Bring a stored session up to the current shape.
 *
 * Merchant normalization runs at import time, so transactions written before
 * it existed keep their raw descriptors — a tab open across the change would
 * still show "AMERICAN AIR0017412354781 FORT WORTH TX" in every merchant list.
 * Normalizing on load repairs those in place. The absence of `rawMerchant` is
 * what marks a transaction as pre-migration, and setting it makes the pass
 * idempotent.
 */
export function migrate(session: SessionState): SessionState {
  const needsMerchantNormalization = session.transactions.some(
    (t) => t.rawMerchant === undefined
  );
  const normalized = needsMerchantNormalization
    ? {
        ...session,
        transactions: session.transactions.map((t) =>
          t.rawMerchant === undefined
            ? {
                ...t,
                merchant: normalizeMerchant(t.merchant),
                rawMerchant: t.merchant,
              }
            : t
        ),
      }
    : session;

  return dedupeCards(normalized);
}

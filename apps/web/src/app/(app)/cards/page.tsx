"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAccounts, getCards, createCard } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Plus, CreditCard, Building2 } from "lucide-react";
import Link from "next/link";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

export default function CardsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [network, setNetwork] = useState("visa");
  const [annualFee, setAnnualFee] = useState("");

  const { data: accounts = [], isLoading: loadingAccounts } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });

  const { data: cards = [], isLoading: loadingCards } = useQuery({
    queryKey: ["cards"],
    queryFn: getCards,
  });

  const mutation = useMutation({
    mutationFn: createCard,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cards"] });
      setOpen(false);
      resetForm();
    },
    onError: () => {},
  });

  function resetForm() {
    setName("");
    setNetwork("visa");
    setAnnualFee("");
  }

  const creditAccounts = accounts.filter((a) => a.type === "credit");
  const isLoading = loadingAccounts || loadingCards;
  const hasAny = creditAccounts.length > 0 || cards.length > 0;

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">Cards</h1>
          <p className="text-sm text-muted mt-1">
            {isLoading ? (
              <span className="inline-block h-4 w-36 bg-muted rounded animate-pulse align-middle" />
            ) : (
              "Your credit cards"
            )}
          </p>
        </div>
        <Dialog
          open={open}
          onOpenChange={(o) => {
            setOpen(o);
            if (!o) {
              resetForm();
              mutation.reset();
            }
          }}
        >
          <DialogTrigger className="flex items-center gap-2 bg-foreground text-background px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity active:translate-y-px">
            <Plus className="w-4 h-4" />
            Add Card
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Add Card</DialogTitle>
              <DialogDescription>
                Add a credit card to track rewards and spending.
              </DialogDescription>
            </DialogHeader>
            <form
              id="add-card-form"
              onSubmit={(e) => {
                e.preventDefault();
                mutation.mutate({
                  name,
                  network,
                  annual_fee: parseFloat(annualFee) || 0,
                });
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-1 gap-4">
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Card Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                    placeholder="e.g. Chase Sapphire Preferred"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Network
                  </label>
                  <select
                    value={network}
                    onChange={(e) => setNetwork(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                  >
                    <option value="visa">Visa</option>
                    <option value="mastercard">Mastercard</option>
                    <option value="amex">Amex</option>
                    <option value="discover">Discover</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Annual Fee
                  </label>
                  <input
                    type="number"
                    step="1"
                    value={annualFee}
                    onChange={(e) => setAnnualFee(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                    placeholder="0"
                  />
                </div>
              </div>
              {mutation.isError && (
                <p className="text-sm text-red-500">
                  Failed to add card. Please try again.
                </p>
              )}
            </form>
            <DialogFooter>
              <button
                type="submit"
                form="add-card-form"
                disabled={mutation.isPending}
                className="bg-foreground text-background px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity active:translate-y-px"
              >
                {mutation.isPending ? "Adding..." : "Add Card"}
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[...Array(2)].map((_, i) => (
            <div
              key={i}
              className="bg-gradient-to-br from-slate-800 to-slate-950 rounded-xl p-6 animate-pulse"
            >
              <div className="flex justify-between items-start mb-8">
                <div className="h-3 w-16 bg-slate-700 rounded" />
                <div className="w-8 h-8 bg-slate-700 rounded" />
              </div>
              <div className="h-5 w-40 bg-slate-700 rounded mb-2" />
              <div className="h-4 w-28 bg-slate-700 rounded" />
            </div>
          ))}
        </div>
      ) : !hasAny ? (
        <div className="text-center py-12 bg-card rounded-xl border border-border">
          <CreditCard className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
          <p className="text-sm font-medium text-muted">No cards yet.</p>
          <p className="text-muted-foreground text-sm mt-1 leading-relaxed">
            Add a card manually or connect via Plaid in{" "}
            <Link
              href="/settings"
              className="underline underline-offset-2 hover:text-foreground transition-colors"
            >
              Settings
            </Link>
            .
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {creditAccounts.length > 0 && (
            <div>
              <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                Linked via Plaid
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {creditAccounts.map((acct) => (
                  <div
                    key={`plaid-${acct.id}`}
                    className="bg-gradient-to-br from-slate-800 to-slate-950 rounded-xl p-6 text-white"
                  >
                    <div className="flex justify-between items-start mb-8">
                      <div className="text-xs font-medium tracking-widest uppercase opacity-70">
                        {acct.institution_name || "Credit Card"}
                      </div>
                      <Building2 className="w-6 h-6 opacity-40" />
                    </div>
                    <div className="text-base font-semibold tracking-tight mb-1">
                      {acct.name}
                    </div>
                    <div className="text-sm font-mono tabular-nums opacity-60">
                      Balance: {formatCurrency(Math.abs(acct.balance))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {cards.length > 0 && (
            <div>
              <h2 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                Added manually
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {cards.map((card) => (
                  <div
                    key={`manual-${card.id}`}
                    className="bg-gradient-to-br from-slate-800 to-slate-950 rounded-xl p-6 text-white"
                  >
                    <div className="flex justify-between items-start mb-8">
                      <div className="text-xs font-medium tracking-widest uppercase opacity-70">
                        {card.network || "Card"}
                      </div>
                      <CreditCard className="w-8 h-8 opacity-40" />
                    </div>
                    <div className="text-base font-semibold tracking-tight mb-1">
                      {card.name}
                    </div>
                    <div className="text-sm font-mono tabular-nums opacity-60">
                      Annual fee: {formatCurrency(card.annual_fee)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

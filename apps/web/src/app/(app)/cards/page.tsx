"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getAccounts,
  getCards,
  createCard,
  updateCard,
  deleteCard,
} from "@/lib/api";
import type { Card } from "@/lib/types";
import { formatCurrency } from "@/lib/format";
import { Plus, CreditCard, Building2, Pencil, Trash2 } from "lucide-react";
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
    <div>
      <div className="flex items-center justify-end mb-6">
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
          <DialogTrigger className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary-hover transition-colors active:translate-y-px">
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
                <p className="text-sm text-destructive">
                  Failed to add card. Please try again.
                </p>
              )}
            </form>
            <DialogFooter>
              <button
                type="submit"
                form="add-card-form"
                disabled={mutation.isPending}
                className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-hover disabled:opacity-50 transition-colors active:translate-y-px"
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
              className="bg-card rounded-lg border border-border p-5 animate-pulse"
            >
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-accent" />
                <div className="flex-1">
                  <div className="h-4 w-40 bg-accent rounded mb-2" />
                  <div className="h-3 w-24 bg-accent rounded mb-3" />
                  <div className="h-4 w-28 bg-accent rounded" />
                </div>
              </div>
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
                    className="bg-card rounded-lg border border-border p-5 flex items-start gap-4"
                  >
                    <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Building2 className="w-5 h-5 text-primary" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-0.5">
                        <p className="font-medium text-sm text-card-foreground truncate">
                          {acct.name}
                        </p>
                        <span className="flex-shrink-0 inline-flex items-center rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-medium text-success">
                          ✓ Linked
                        </span>
                      </div>
                      <p className="text-xs text-muted truncate">
                        {acct.institution_name || "Credit Card"}
                      </p>
                      <p className="mt-2 text-sm font-mono tabular-nums text-card-foreground">
                        {formatCurrency(Math.abs(acct.balance))}
                        <span className="text-muted"> balance</span>
                      </p>
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
                  <ManualCardItem key={`manual-${card.id}`} card={card} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ManualCardItem({ card }: { card: Card }) {
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [name, setName] = useState(card.name);
  const [network, setNetwork] = useState(card.network || "visa");
  const [annualFee, setAnnualFee] = useState(String(card.annual_fee));

  // Card fields feed the recommendation engine's existing-card math, so refresh
  // recommendations alongside the card grid on any change. The ["recommendations"]
  // prefix covers next-card / portfolio / spending-profile sub-queries.
  function invalidateAll() {
    queryClient.invalidateQueries({ queryKey: ["cards"] });
    queryClient.invalidateQueries({ queryKey: ["recommendations"] });
  }

  const editMutation = useMutation({
    mutationFn: () =>
      updateCard(card.id, {
        name,
        network,
        annual_fee: parseFloat(annualFee) || 0,
      }),
    onSuccess: () => {
      invalidateAll();
      setEditOpen(false);
    },
    onError: () => {},
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteCard(card.id),
    onSuccess: () => {
      invalidateAll();
      setConfirmingDelete(false);
    },
    onError: () => {},
  });

  function resetEditForm() {
    setName(card.name);
    setNetwork(card.network || "visa");
    setAnnualFee(String(card.annual_fee));
  }

  return (
    <div className="bg-card rounded-lg border border-border p-5">
      <div className="flex items-start gap-4">
        <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
          <CreditCard className="w-5 h-5 text-primary" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium text-sm text-card-foreground truncate">
            {card.name}
          </p>
          <p className="text-xs text-muted capitalize truncate">
            {card.network || "Card"}
          </p>
          <p className="mt-2 text-sm font-mono tabular-nums text-card-foreground">
            {formatCurrency(card.annual_fee)}
            <span className="text-muted"> / yr annual fee</span>
          </p>
        </div>
        <div className="flex items-center gap-1">
          <Dialog
            open={editOpen}
            onOpenChange={(o) => {
              setEditOpen(o);
              if (!o) {
                resetEditForm();
                editMutation.reset();
              }
            }}
          >
            <DialogTrigger
              aria-label="Edit card"
              className="p-1.5 rounded-md text-muted hover:bg-accent hover:text-card-foreground transition-colors"
            >
              <Pencil className="w-4 h-4" />
            </DialogTrigger>
            <DialogContent className="sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Edit Card</DialogTitle>
                <DialogDescription>
                  Update this card&apos;s details.
                </DialogDescription>
              </DialogHeader>
              <form
                id={`edit-card-form-${card.id}`}
                onSubmit={(e) => {
                  e.preventDefault();
                  editMutation.mutate();
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
                {editMutation.isError && (
                  <p className="text-sm text-destructive">
                    Failed to save changes. Please try again.
                  </p>
                )}
              </form>
              <DialogFooter>
                <button
                  type="submit"
                  form={`edit-card-form-${card.id}`}
                  disabled={editMutation.isPending}
                  className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-hover disabled:opacity-50 transition-colors active:translate-y-px"
                >
                  {editMutation.isPending ? "Saving..." : "Save Changes"}
                </button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <button
            type="button"
            aria-label="Delete card"
            onClick={() => setConfirmingDelete(true)}
            className="p-1.5 rounded-md text-muted hover:bg-accent hover:text-destructive transition-colors"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      {confirmingDelete && (
        <div className="mt-4 pt-4 border-t border-border">
          <p className="text-sm text-muted mb-3">Delete this card?</p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => deleteMutation.mutate()}
              disabled={deleteMutation.isPending}
              className="bg-destructive/10 text-destructive px-3 py-1.5 rounded-md text-sm font-medium hover:bg-destructive/20 disabled:opacity-50 transition-colors"
            >
              {deleteMutation.isPending ? "Deleting..." : "Delete"}
            </button>
            <button
              type="button"
              onClick={() => setConfirmingDelete(false)}
              disabled={deleteMutation.isPending}
              className="px-3 py-1.5 rounded-md text-sm font-medium text-muted hover:bg-accent hover:text-card-foreground transition-colors"
            >
              Cancel
            </button>
          </div>
          {deleteMutation.isError && (
            <p className="text-sm text-destructive mt-2">
              Failed to delete. Please try again.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

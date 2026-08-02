"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getAccounts, createAccount } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/format";
import { Plus, Check, ArrowRight } from "lucide-react";

import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

const ACCOUNT_TYPES = ["checking", "savings", "credit", "investment", "loan"];

export default function AccountsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [type, setType] = useState("checking");
  const [institution, setInstitution] = useState("");
  const [balance, setBalance] = useState("");

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });

  const mutation = useMutation({
    mutationFn: createAccount,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      setOpen(false);
      resetForm();
    },
    onError: () => {},
  });

  function resetForm() {
    setName("");
    setType("checking");
    setInstitution("");
    setBalance("");
  }

  const totalBalance = accounts.reduce((sum, a) => sum + a.balance, 0);

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">
            Accounts
          </h1>
          <p className="text-sm text-muted mt-1">
            {isLoading ? (
              <span className="inline-block h-4 w-28 bg-accent rounded animate-pulse align-middle" />
            ) : (
              <>
                Total balance:{" "}
                <span className="font-mono tabular-nums font-medium">
                  {formatCurrency(totalBalance)}
                </span>
              </>
            )}
          </p>
        </div>
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) resetForm(); }}>
          <DialogTrigger className="flex items-center gap-2 bg-primary text-primary-foreground px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-primary-hover motion-base active:translate-y-px">
            <Plus className="w-4 h-4" />
            Add Account
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>Add Account</DialogTitle>
              <DialogDescription>
                Add a new financial account to track.
              </DialogDescription>
            </DialogHeader>
            <form
              id="add-account-form"
              onSubmit={(e) => {
                e.preventDefault();
                mutation.mutate({
                  name,
                  type,
                  institution_name: institution || undefined,
                  balance: parseFloat(balance) || 0,
                });
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
                    placeholder="e.g. Chase Checking"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Type
                  </label>
                  <select
                    value={type}
                    onChange={(e) => setType(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
                  >
                    {ACCOUNT_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {t.charAt(0).toUpperCase() + t.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Institution
                  </label>
                  <input
                    type="text"
                    value={institution}
                    onChange={(e) => setInstitution(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
                    placeholder="e.g. Chase"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Balance
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={balance}
                    onChange={(e) => setBalance(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
                    placeholder="0.00"
                  />
                </div>
              </div>
              {mutation.isError && (
                <p className="text-sm text-destructive">
                  Failed to create account. Please try again.
                </p>
              )}
            </form>
            <DialogFooter>
              <button
                type="submit"
                form="add-account-form"
                disabled={mutation.isPending}
                className="bg-primary text-primary-foreground px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-hover disabled:opacity-50 motion-base active:translate-y-px"
              >
                {mutation.isPending ? "Creating..." : "Create Account"}
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="space-y-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="bg-card rounded-xl border border-border p-5 flex items-center justify-between animate-pulse"
            >
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-lg bg-accent" />
                <div className="space-y-2">
                  <div className="h-4 w-32 bg-accent rounded" />
                  <div className="h-3 w-48 bg-accent rounded" />
                </div>
              </div>
              <div className="h-5 w-24 bg-accent rounded" />
            </div>
          ))}
        </div>
      ) : (
        /* Panel cards: title row, hairline rule, then label/value rows \u2014 with
           an arrow revealed on hover, and a dashed placeholder to add one. */
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {accounts.map((account) => (
            <div key={account.id} className="panel-link" tabIndex={0}>
              <div className="panel">
                <div className="panel-head">
                  <span className="font-medium text-[15px] text-card-foreground truncate">
                    {account.name}
                  </span>
                  <ArrowRight className="hover-arrow w-4 h-4 flex-shrink-0 text-muted" />
                </div>
                <div className="panel-body">
                  <div className="panel-row">
                    <span className="panel-label">Institution</span>
                    <span className="panel-value truncate">
                      {account.institution_name || "\u2014"}
                    </span>
                  </div>
                  <div className="panel-row">
                    <span className="panel-label">Type</span>
                    <span className="mono-chip capitalize">{account.type}</span>
                  </div>
                  <div className="panel-row">
                    <span className="panel-label">Balance</span>
                    <span
                      className={`panel-value font-mono font-medium ${account.balance < 0 ? "text-destructive" : ""}`}
                    >
                      {formatCurrency(account.balance)}
                    </span>
                  </div>
                  <div className="panel-row">
                    <span className="panel-label">Last synced</span>
                    <span className="panel-value">
                      {account.last_synced_at ? (
                        <span className="inline-flex items-center gap-1 text-success">
                          <Check className="w-3.5 h-3.5" />
                          {formatDate(account.last_synced_at)}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">Never</span>
                      )}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          ))}
          {/* Dashed placeholder mirroring the reference's "create" tile. */}
          <button
            type="button"
            onClick={() => setOpen(true)}
            className="dashed-card"
          >
            <Plus className="w-5 h-5" />
            <span className="text-sm font-medium">Add Account</span>
          </button>
        </div>
      )}
    </div>
  );
}

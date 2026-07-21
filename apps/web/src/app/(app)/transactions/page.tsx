"use client";

import { useEffect, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getTransactions, getAccounts, updateTransaction } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Search } from "lucide-react";
import { StatementImport } from "@/components/statement-import";

// The fixed internal category set — must stay in sync with the backend taxonomy
// (`apps/api/app/services/enrichment/taxonomy.py`). Editing a transaction's
// category drives the spending profile (dining is the Phase-2 headline metric).
const TAXONOMY_CATEGORIES = [
  "dining",
  "groceries",
  "travel",
  "transport",
  "shopping",
  "bills",
  "entertainment",
  "health",
  "income",
  "other",
] as const;

export default function TransactionsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [filterAccount, setFilterAccount] = useState<number | undefined>();
  const [filterCategory, setFilterCategory] = useState<string | undefined>();
  const [savingId, setSavingId] = useState<number | null>(null);

  const { data: transactions = [], isLoading } = useQuery({
    queryKey: ["transactions", filterAccount, filterCategory],
    queryFn: () =>
      getTransactions({
        account_id: filterAccount,
        category: filterCategory,
      }),
  });

  // Editing a category PATCHes the transaction; the backend fires
  // TRANSACTION_MUTATED, which recomputes the spending profile + insights, so we
  // invalidate those consumers too and the "you dine out ~N×/month" figure
  // self-corrects.
  const recategorize = useMutation({
    mutationFn: ({ id, category }: { id: number; category: string }) =>
      updateTransaction(id, { category }),
    onMutate: ({ id }) => setSavingId(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      queryClient.invalidateQueries({ queryKey: ["insights"] });
      queryClient.invalidateQueries({ queryKey: ["insights-summary"] });
    },
    onSettled: () => setSavingId(null),
  });

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });

  const categories = [
    ...new Set(transactions.map((t) => t.category).filter(Boolean)),
  ].sort();

  const accountMap = Object.fromEntries(accounts.map((a) => [a.id, a.name]));

  const filtered = search
    ? transactions.filter(
        (t) =>
          t.merchant.toLowerCase().includes(search.toLowerCase()) ||
          (t.category || "").toLowerCase().includes(search.toLowerCase())
      )
    : transactions;

  const sorted = [...filtered].sort(
    (a, b) =>
      new Date(b.occurred_on).getTime() - new Date(a.occurred_on).getTime()
  );

  // Paginate the (filtered, sorted) list so long statements stay scannable.
  const PAGE_SIZE = 25;
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const currentPage = Math.min(page, totalPages);
  const paged = sorted.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );
  // Jump back to page 1 whenever the filters/search change the result set.
  useEffect(() => {
    setPage(1);
  }, [search, filterAccount, filterCategory]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Transactions
        </h1>
        <p className="text-sm text-muted mt-1">
          {isLoading ? (
            <span className="inline-block h-4 w-24 bg-muted rounded animate-pulse align-middle" />
          ) : (
            <>
              <span className="font-mono tabular-nums">
                {transactions.length}
              </span>{" "}
              transactions
            </>
          )}
        </p>
      </div>

      <StatementImport />

      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search merchants..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-input bg-background text-foreground rounded-lg pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
          />
        </div>
        <select
          value={filterAccount ?? ""}
          onChange={(e) =>
            setFilterAccount(e.target.value ? Number(e.target.value) : undefined)
          }
          className="border border-input bg-background text-foreground rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
        >
          <option value="">All Accounts</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <select
          value={filterCategory ?? ""}
          onChange={(e) => setFilterCategory(e.target.value || undefined)}
          className="border border-input bg-background text-foreground rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
        >
          <option value="">All Categories</option>
          {categories.map((c) => (
            <option key={c} value={c!}>
              {c}
            </option>
          ))}
        </select>
      </div>

      {recategorize.isError && (
        <div className="mb-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-500">
          Couldn&apos;t update the category. Please try again.
        </div>
      )}

      <div className="bg-card rounded-xl border border-border overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border text-left">
              <th className="px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Date
              </th>
              <th className="px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Merchant
              </th>
              <th className="px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Category
              </th>
              <th className="px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider">
                Account
              </th>
              <th className="px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider text-right">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading
              ? [...Array(6)].map((_, i) => (
                  <tr
                    key={i}
                    className="border-b border-border last:border-0 animate-pulse"
                  >
                    <td className="px-5 py-3">
                      <div className="h-4 w-20 bg-muted rounded" />
                    </td>
                    <td className="px-5 py-3">
                      <div className="h-4 w-28 bg-muted rounded" />
                    </td>
                    <td className="px-5 py-3">
                      <div className="h-5 w-16 bg-muted rounded" />
                    </td>
                    <td className="px-5 py-3">
                      <div className="h-4 w-24 bg-muted rounded" />
                    </td>
                    <td className="px-5 py-3 flex justify-end">
                      <div className="h-4 w-16 bg-muted rounded" />
                    </td>
                  </tr>
                ))
              : paged.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-border last:border-0 hover:bg-accent/30 transition-colors"
                  >
                    <td className="px-5 py-3 text-sm text-muted font-mono tabular-nums">
                      {t.occurred_on}
                    </td>
                    <td className="px-5 py-3 text-sm font-medium text-card-foreground">
                      {t.merchant}
                    </td>
                    <td className="px-5 py-3">
                      <select
                        aria-label="Category"
                        value={t.category ?? "other"}
                        disabled={savingId === t.id}
                        onChange={(e) =>
                          recategorize.mutate({
                            id: t.id,
                            category: e.target.value,
                          })
                        }
                        className="border border-input bg-background text-foreground rounded-lg px-2 py-1 text-xs capitalize focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors disabled:opacity-50 disabled:cursor-wait"
                      >
                        {TAXONOMY_CATEGORIES.map((c) => (
                          <option key={c} value={c} className="capitalize">
                            {c}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td className="px-5 py-3 text-sm text-muted">
                      {accountMap[t.account_id] || `#${t.account_id}`}
                    </td>
                    <td
                      className={`px-5 py-3 text-sm font-mono font-medium tabular-nums text-right ${t.is_income ? "text-emerald-500" : "text-card-foreground"}`}
                    >
                      {t.is_income ? "+" : "-"}
                      {formatCurrency(Math.abs(t.amount))}
                    </td>
                  </tr>
                ))}
          </tbody>
        </table>
      </div>

      {!isLoading && sorted.length > PAGE_SIZE && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <span className="text-muted">
            Showing{" "}
            <span className="font-mono tabular-nums">
              {(currentPage - 1) * PAGE_SIZE + 1}–
              {Math.min(currentPage * PAGE_SIZE, sorted.length)}
            </span>{" "}
            of{" "}
            <span className="font-mono tabular-nums">{sorted.length}</span>
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={currentPage <= 1}
              className="px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-muted font-mono tabular-nums">
              {currentPage} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage >= totalPages}
              className="px-3 py-1.5 rounded-lg border border-border text-sm hover:bg-accent/40 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

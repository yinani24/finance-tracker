"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getTransactions, getAccounts } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Search } from "lucide-react";

export default function TransactionsPage() {
  const [search, setSearch] = useState("");
  const [filterAccount, setFilterAccount] = useState<number | undefined>();
  const [filterCategory, setFilterCategory] = useState<string | undefined>();

  const { data: transactions = [], isLoading } = useQuery({
    queryKey: ["transactions", filterAccount, filterCategory],
    queryFn: () =>
      getTransactions({
        account_id: filterAccount,
        category: filterCategory,
      }),
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
              : sorted.map((t) => (
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
                      {t.category && (
                        <span className="inline-block px-2 py-0.5 bg-accent text-muted rounded text-xs capitalize">
                          {t.category.replace(/_/g, " ")}
                        </span>
                      )}
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
    </div>
  );
}

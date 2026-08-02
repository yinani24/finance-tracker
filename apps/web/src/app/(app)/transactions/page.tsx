"use client";

import { useEffect, useMemo, useState } from "react";
import { formatCurrency } from "@/lib/format";
import { Search, Plus, X } from "lucide-react";
import { useSession } from "@/lib/session/session-context";
import { StatementDropzone } from "@/components/statement-dropzone";

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
  const { session, ready, updateTransaction } = useSession();
  const [search, setSearch] = useState("");
  const [filterCard, setFilterCard] = useState<string | undefined>();
  const [filterCategory, setFilterCategory] = useState<string | undefined>();
  // The dropzone is opened on demand: once transactions exist, the table is
  // the point of the page and a permanent upload panel just pushes it down.
  const [importing, setImporting] = useState(false);

  const { transactions, heldCards } = session;
  const cardMap = Object.fromEntries(heldCards.map((c) => [c.id, c.name]));

  const sorted = useMemo(() => {
    const needle = search.toLowerCase();
    return transactions
      .filter((t) => !filterCard || t.sourceId === filterCard)
      .filter((t) => !filterCategory || t.category === filterCategory)
      .filter(
        (t) =>
          !needle ||
          t.merchant.toLowerCase().includes(needle) ||
          t.category.toLowerCase().includes(needle)
      )
      .sort((a, b) => b.occurredOn.localeCompare(a.occurredOn));
  }, [transactions, search, filterCard, filterCategory]);

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
  }, [search, filterCard, filterCategory]);

  const empty = ready && transactions.length === 0;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">
            Transactions
          </h1>
          <p className="text-sm text-muted mt-1">
            {!ready ? (
              <span className="inline-block h-4 w-24 bg-accent rounded animate-pulse align-middle" />
            ) : (
              <>
                <span className="font-mono tabular-nums">
                  {transactions.length}
                </span>{" "}
                transactions, read in this tab
              </>
            )}
          </p>
        </div>
        {!empty && (
          <button
            type="button"
            onClick={() => setImporting((v) => !v)}
            className="motion-base flex flex-shrink-0 items-center gap-2 border border-border px-3 py-2 text-sm hover:bg-accent/40"
          >
            {importing ? (
              <>
                <X className="h-4 w-4" /> Close
              </>
            ) : (
              <>
                <Plus className="h-4 w-4" /> Add a statement
              </>
            )}
          </button>
        )}
      </div>

      {(empty || importing) && (
        <div className="mb-6">
          <StatementDropzone
            compact={!empty}
            onIngested={() => setImporting(false)}
          />
        </div>
      )}

      {!empty && (
        <>
          <div className="flex flex-wrap gap-3 mb-6">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search merchants..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full border border-input bg-background text-foreground pl-9 pr-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
              />
            </div>
            {heldCards.length > 1 && (
              <select
                value={filterCard ?? ""}
                onChange={(e) => setFilterCard(e.target.value || undefined)}
                className="border border-input bg-background text-foreground px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
              >
                <option value="">All cards</option>
                {heldCards.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            )}
          </div>

          {/* Segmented pill filters — the taxonomy is a small fixed set, so a
              visible toggle row beats a dropdown that hides every option. */}
          <div className="flex flex-wrap items-center gap-5 mb-6 border-b border-border">
            {[null, ...TAXONOMY_CATEGORIES].map((c) => {
              const active = c === null ? !filterCategory : filterCategory === c;
              return (
                <button
                  key={c ?? "all"}
                  type="button"
                  onClick={() => setFilterCategory(c ?? undefined)}
                  data-active={active}
                  className={
                    "relative -mb-px border-b-2 pb-2.5 pt-1 text-[13px] font-medium capitalize motion-base " +
                    (active
                      ? "border-primary text-card-foreground"
                      : "border-transparent text-muted hover:text-card-foreground")
                  }
                >
                  {c ?? "All"}
                </button>
              );
            })}
          </div>

          <div className="border border-border overflow-hidden">
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
                    Card
                  </th>
                  <th className="px-5 py-3 text-xs font-medium text-muted-foreground uppercase tracking-wider text-right">
                    Amount
                  </th>
                </tr>
              </thead>
              <tbody>
                {paged.map((t) => {
                  const income = t.amount > 0;
                  return (
                    <tr
                      key={t.id}
                      className="row-interactive border-b border-border last:border-0 hover:bg-accent/30"
                    >
                      <td className="px-5 py-3 text-sm text-muted font-mono tabular-nums">
                        {t.occurredOn}
                      </td>
                      <td className="px-5 py-3 text-sm font-medium text-card-foreground">
                        {t.merchant}
                      </td>
                      <td className="px-5 py-3">
                        <select
                          aria-label="Category"
                          value={t.category}
                          onChange={(e) =>
                            updateTransaction(t.id, { category: e.target.value })
                          }
                          className="border border-input bg-background text-foreground px-2 py-1 text-xs capitalize focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
                        >
                          {TAXONOMY_CATEGORIES.map((c) => (
                            <option key={c} value={c} className="capitalize">
                              {c}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="px-5 py-3 text-sm text-muted">
                        {t.sourceId ? cardMap[t.sourceId] ?? "—" : "—"}
                      </td>
                      <td
                        className={`px-5 py-3 text-sm font-mono font-medium tabular-nums text-right ${income ? "text-success" : "text-card-foreground"}`}
                      >
                        {income ? "+" : "-"}
                        {formatCurrency(Math.abs(t.amount))}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {sorted.length > PAGE_SIZE && (
            <div className="flex items-center justify-between mt-4 text-sm">
              <span className="text-muted">
                Showing{" "}
                <span className="font-mono tabular-nums">
                  {(currentPage - 1) * PAGE_SIZE + 1}–
                  {Math.min(currentPage * PAGE_SIZE, sorted.length)}
                </span>{" "}
                of <span className="font-mono tabular-nums">{sorted.length}</span>
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={currentPage <= 1}
                  className="motion-base px-3 py-1.5 border border-border text-sm hover:bg-accent/40 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="text-muted font-mono tabular-nums">
                  {currentPage} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={currentPage >= totalPages}
                  className="motion-base px-3 py-1.5 border border-border text-sm hover:bg-accent/40 disabled:opacity-40 disabled:cursor-not-allowed"
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

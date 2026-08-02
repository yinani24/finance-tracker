"use client";

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createImport, getAccounts, getImports } from "@/lib/api";
import type { ImportSummary } from "@/lib/types";
import { Upload } from "lucide-react";

// Surfaces the statement-import backend (POST/GET /imports) in the UI: upload a
// CSV bank/card statement for an account and the backend parses + dedupes it
// into transactions. This is the keys-free path to get real transaction history
// in (Plaid needs live linking), and it feeds the spending profile + insights —
// so on success we invalidate those queries, mirroring inline recategorization.
const IMPORTS_PER_PAGE = 5;

export function StatementImport() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [accountId, setAccountId] = useState<number | undefined>();
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);
  // Recent imports accumulate, so page them rather than truncating at 5.
  const [importPage, setImportPage] = useState(1);

  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });

  const { data: imports = [] } = useQuery({
    queryKey: ["imports"],
    queryFn: getImports,
  });

  const mutation = useMutation({
    mutationFn: ({ id, f }: { id: number; f: File }) => createImport(id, f),
    onSuccess: (result) => {
      setSummary(result);
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      // The new transactions change every downstream signal — refresh them all.
      queryClient.invalidateQueries({ queryKey: ["imports"] });
      queryClient.invalidateQueries({ queryKey: ["transactions"] });
      queryClient.invalidateQueries({ queryKey: ["accounts"] });
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
      queryClient.invalidateQueries({ queryKey: ["spending-profile"] });
      queryClient.invalidateQueries({ queryKey: ["insights"] });
      queryClient.invalidateQueries({ queryKey: ["insights-summary"] });
    },
  });

  const canSubmit = accountId !== undefined && file !== null && !mutation.isPending;

  const handleSubmit = () => {
    if (accountId === undefined || file === null) return;
    setSummary(null);
    mutation.mutate({ id: accountId, f: file });
  };

  const importPages = Math.max(1, Math.ceil(imports.length / IMPORTS_PER_PAGE));
  const currentImportPage = Math.min(importPage, importPages);
  const pagedImports = imports.slice(
    (currentImportPage - 1) * IMPORTS_PER_PAGE,
    currentImportPage * IMPORTS_PER_PAGE
  );

  return (
    <div className="bg-card rounded-xl border border-border p-5 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <Upload className="w-4 h-4 text-muted-foreground" />
        <h2 className="font-semibold text-card-foreground">Import statement</h2>
      </div>
      <p className="text-sm text-muted mb-4">
        Upload a bank or card statement (CSV or PDF) to add transactions. Duplicates are
        detected and skipped, so re-uploading an overlapping export is safe.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={accountId ?? ""}
          onChange={(e) =>
            setAccountId(e.target.value ? Number(e.target.value) : undefined)
          }
          className="border border-input bg-background text-foreground rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring motion-base"
        >
          <option value="">Select account…</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>

        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.pdf,text/csv,application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-foreground file:mr-3 file:rounded-lg file:border file:border-input file:bg-background file:px-3 file:py-2 file:text-sm file:text-foreground hover:file:bg-accent"
        />

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary-hover motion-base"
        >
          {mutation.isPending ? "Importing…" : "Import"}
        </button>
      </div>

      {mutation.isError && (
        <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Import failed"}
        </div>
      )}

      {summary && (
        <div className="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-2.5 text-sm text-card-foreground">
          Imported <span className="font-medium">{summary.added}</span> new
          transaction{summary.added === 1 ? "" : "s"} from {summary.total_rows} row
          {summary.total_rows === 1 ? "" : "s"} · {summary.duplicates} duplicate
          {summary.duplicates === 1 ? "" : "s"} skipped
          {summary.skipped > 0 ? ` · ${summary.skipped} unparseable` : ""}.
          {summary.errors.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-muted hover:text-card-foreground">
                Show {summary.errors.length} unparseable row
                {summary.errors.length === 1 ? "" : "s"}
              </summary>
              <ul className="mt-1.5 space-y-0.5 text-xs text-muted">
                {summary.errors.map((e) => (
                  <li key={e.row} className="font-mono">
                    Row {e.row}: {e.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}

      {imports.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-medium text-muted uppercase tracking-wide mb-2">
            Recent imports
          </div>
          <div className="overflow-x-auto border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Date</th>
                  <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Account</th>
                  <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Type</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Txns</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Status</th>
                </tr>
              </thead>
              <tbody>
                {pagedImports.map((imp) => (
                  <tr
                    key={imp.id}
                    className="border-b border-border last:border-0 motion-base hover:bg-accent/40"
                  >
                    <td className="px-3 py-2 font-mono tabular-nums text-muted whitespace-nowrap">
                      {new Date(imp.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-3 py-2 text-card-foreground truncate max-w-[180px]">
                      {accounts.find((a) => a.id === imp.account_id)?.name ?? "—"}
                    </td>
                    <td className="px-3 py-2">
                      <span className="mono-chip uppercase">{imp.import_type}</span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums text-card-foreground">
                      {imp.transaction_count}
                    </td>
                    <td
                      className={
                        "px-3 py-2 text-right whitespace-nowrap " +
                        (imp.status === "failed"
                          ? "text-destructive"
                          : "text-success")
                      }
                    >
                      {imp.status}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {importPages > 1 && (
            <div className="mt-2 flex items-center justify-between text-xs">
              <span className="text-muted">
                <span className="font-mono tabular-nums">
                  {(currentImportPage - 1) * IMPORTS_PER_PAGE + 1}–
                  {Math.min(currentImportPage * IMPORTS_PER_PAGE, imports.length)}
                </span>{" "}
                of <span className="font-mono tabular-nums">{imports.length}</span>
              </span>
              <span className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setImportPage((p) => Math.max(1, p - 1))}
                  disabled={currentImportPage <= 1}
                  className="rounded border border-border px-2 py-1 motion-base hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Previous
                </button>
                <span className="font-mono tabular-nums text-muted">
                  {currentImportPage} / {importPages}
                </span>
                <button
                  type="button"
                  onClick={() => setImportPage((p) => Math.min(importPages, p + 1))}
                  disabled={currentImportPage >= importPages}
                  className="rounded border border-border px-2 py-1 motion-base hover:bg-accent disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  Next
                </button>
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

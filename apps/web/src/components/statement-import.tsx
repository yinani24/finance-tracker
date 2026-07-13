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
export function StatementImport() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [accountId, setAccountId] = useState<number | undefined>();
  const [file, setFile] = useState<File | null>(null);
  const [summary, setSummary] = useState<ImportSummary | null>(null);

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

  return (
    <div className="bg-card rounded-xl border border-border p-5 mb-6">
      <div className="flex items-center gap-2 mb-1">
        <Upload className="w-4 h-4 text-muted-foreground" />
        <h2 className="font-semibold text-card-foreground">Import CSV statement</h2>
      </div>
      <p className="text-sm text-muted mb-4">
        Upload a bank or card statement (CSV) to add transactions. Duplicates are
        detected and skipped, so re-uploading an overlapping export is safe.
      </p>

      <div className="flex flex-wrap items-center gap-3">
        <select
          value={accountId ?? ""}
          onChange={(e) =>
            setAccountId(e.target.value ? Number(e.target.value) : undefined)
          }
          className="border border-input bg-background text-foreground rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
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
          accept=".csv,text/csv"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-foreground file:mr-3 file:rounded-lg file:border file:border-input file:bg-background file:px-3 file:py-2 file:text-sm file:text-foreground hover:file:bg-muted/10"
        />

        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          className="rounded-lg bg-primary text-primary-foreground px-4 py-2.5 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
        >
          {mutation.isPending ? "Importing…" : "Import"}
        </button>
      </div>

      {mutation.isError && (
        <div className="mt-4 rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm text-red-500">
          {mutation.error instanceof Error
            ? mutation.error.message
            : "Import failed"}
        </div>
      )}

      {summary && (
        <div className="mt-4 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2.5 text-sm text-card-foreground">
          Imported <span className="font-medium">{summary.added}</span> new
          transaction{summary.added === 1 ? "" : "s"} from {summary.total_rows} row
          {summary.total_rows === 1 ? "" : "s"} · {summary.duplicates} duplicate
          {summary.duplicates === 1 ? "" : "s"} skipped
          {summary.skipped > 0 ? ` · ${summary.skipped} unparseable` : ""}.
        </div>
      )}

      {imports.length > 0 && (
        <div className="mt-4">
          <div className="text-xs font-medium text-muted uppercase tracking-wide mb-2">
            Recent imports
          </div>
          <ul className="text-sm text-card-foreground divide-y divide-border">
            {imports.slice(0, 5).map((imp) => (
              <li key={imp.id} className="flex items-center justify-between py-2">
                <span className="text-muted">
                  {new Date(imp.created_at).toLocaleDateString()} ·{" "}
                  {imp.import_type.toUpperCase()}
                </span>
                <span className="flex items-center gap-3">
                  <span className="font-mono tabular-nums">
                    {imp.transaction_count} txns
                  </span>
                  <span
                    className={
                      imp.status === "completed"
                        ? "text-emerald-500"
                        : imp.status === "failed"
                          ? "text-red-500"
                          : "text-muted"
                    }
                  >
                    {imp.status}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

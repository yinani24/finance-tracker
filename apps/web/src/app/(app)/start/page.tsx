"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Upload, Loader2, Check, AlertTriangle } from "lucide-react";
import { useSession } from "@/lib/session/session-context";
import { formatCurrency } from "@/lib/format";
import { parseStatement, categorize } from "@/lib/statement";
import {
  parseStatementMetadata,
  statementLabel,
  statementUtilization,
  type StatementMetadata,
} from "@/lib/statement/parse-metadata";
import { extractText } from "@/lib/statement/parse-pdf";

/**
 * Drop-and-go onboarding.
 *
 * A statement already names the card, the issuer, the credit limit and the
 * balance, so asking for them up front was friction we imposed for no reason.
 * Drop a file and everything below is derived: the account, the utilization,
 * the transactions and what they say about spending. Nothing is uploaded —
 * parsing runs in this tab and the results live in session memory only.
 */

interface Detected {
  meta: StatementMetadata;
  added: number;
  errors: number;
  fileName: string;
}

export default function StartPage() {
  const router = useRouter();
  const { session, addCard, addTransactions } = useSession();
  const [busy, setBusy] = useState(false);
  const [detected, setDetected] = useState<Detected[]>([]);
  const [failure, setFailure] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const ingest = useCallback(
    async (files: FileList | File[]) => {
      setBusy(true);
      setFailure(null);
      try {
        for (const file of Array.from(files)) {
          // Read the text once so metadata and transactions agree on the
          // sign convention: a credit-card statement lists charges positive.
          const isPdf =
            file.type === "application/pdf" ||
            file.name.toLowerCase().endsWith(".pdf");
          const meta = isPdf
            ? parseStatementMetadata(
                await extractText(new Uint8Array(await file.arrayBuffer()))
              )
            : ({ isCredit: false } as StatementMetadata);

          const { rows, errors } = await parseStatement(file, {
            isCredit: meta.isCredit,
          });

          if (rows.length === 0) {
            setFailure(
              `Couldn't read any transactions from ${file.name}. If it's a scanned image, the text can't be extracted.`
            );
            continue;
          }

          // The statement told us the account — record it without asking.
          const label = statementLabel(meta);
          const known = session.heldCards.some((c) => c.name === label);
          if (!known && (meta.cardName || meta.issuer || meta.creditLimit)) {
            addCard({
              name: label,
              issuer: meta.issuer,
              creditLimit: meta.creditLimit,
              currentBalance: meta.currentBalance,
            });
          }

          addTransactions(
            rows.map((r) => ({
              occurredOn: r.occurredOn,
              merchant: r.merchant,
              amount: r.signedAmount,
              category: categorize(r.merchant).category,
            })),
            { fileName: file.name, kind: isPdf ? "pdf" : "csv", added: rows.length, errors: errors.length }
          );

          setDetected((d) => [
            ...d,
            { meta, added: rows.length, errors: errors.length, fileName: file.name },
          ]);
        }
      } catch {
        setFailure("That file couldn't be read. CSV and text-based PDF statements work best.");
      } finally {
        setBusy(false);
      }
    },
    [addCard, addTransactions, session.heldCards]
  );

  const total = detected.reduce((s, d) => s + d.added, 0);

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-card-foreground">Drop a statement</h1>
        <p className="mt-1 text-sm text-muted">
          No account, no forms. We read the card, the limit and the spending
          straight out of the file.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer.files?.length) void ingest(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={
          "dashed-card cursor-pointer py-14 " +
          (dragging ? "border-primary bg-accent text-card-foreground" : "")
        }
      >
        {busy ? (
          <>
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="text-sm">Reading your statement…</span>
          </>
        ) : (
          <>
            <Upload className="h-6 w-6" />
            <span className="text-sm font-medium">
              Drop a PDF or CSV statement, or click to choose
            </span>
            <span className="text-xs text-muted-foreground">
              Parsed in this tab — the file never leaves your device
            </span>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.csv,application/pdf,text/csv"
          multiple
          hidden
          onChange={(e) => e.target.files?.length && void ingest(e.target.files)}
        />
      </div>

      {failure && (
        <p className="mt-4 flex items-start gap-2 border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          {failure}
        </p>
      )}

      {detected.length > 0 && (
        <section className="mt-8">
          <h2 className="text-card-foreground">What we found</h2>
          <div className="mt-4 border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Account</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Limit</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Balance</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Used</th>
                  <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">Txns</th>
                </tr>
              </thead>
              <tbody>
                {detected.map((d, i) => {
                  const util = statementUtilization(d.meta);
                  return (
                    <tr key={i} className="border-b border-border last:border-0">
                      <td className="px-3 py-2 text-card-foreground">
                        {statementLabel(d.meta)}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">
                        {d.meta.creditLimit ? formatCurrency(d.meta.creditLimit) : "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums">
                        {d.meta.currentBalance != null
                          ? formatCurrency(d.meta.currentBalance)
                          : "—"}
                      </td>
                      <td
                        className={
                          "px-3 py-2 text-right font-mono tabular-nums " +
                          (util != null && util > 0.3 ? "text-destructive" : "text-muted")
                        }
                      >
                        {util != null ? `${Math.round(util * 100)}%` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right font-mono tabular-nums text-card-foreground">
                        {d.added}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <p className="mt-3 flex items-center gap-2 text-sm text-success">
            <Check className="h-4 w-4" />
            {total} transactions read. Nothing was uploaded.
          </p>

          <button
            onClick={() => router.push("/dashboard")}
            className="mt-6 bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground motion-base hover:bg-primary-hover"
          >
            See what to optimize
          </button>
        </section>
      )}

      <p className="mt-10 flex items-start gap-3 border border-border p-4 text-sm text-muted">
        <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-success" />
        Everything stays in this browser tab and is erased when you close it.
        Nothing is sent to a server or saved to a database.
      </p>
    </div>
  );
}

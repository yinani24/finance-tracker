"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, Loader2, AlertTriangle } from "lucide-react";
import { useSession } from "@/lib/session/session-context";
import type { HeldCard } from "@/lib/session/types";
import { parseStatement, categorize } from "@/lib/statement";
import {
  parseStatementMetadata,
  statementLabel,
  type StatementMetadata,
} from "@/lib/statement/parse-metadata";
import { extractText } from "@/lib/statement/parse-pdf";

/**
 * The one way statements enter the app.
 *
 * Both entry points — first-run onboarding and the import control on the
 * transactions page — used to have their own upload path, and the transactions
 * one still POSTed to `/imports`, which contradicted the client-only promise
 * made two screens earlier. Sharing this component means a file is parsed in
 * the tab and lands in session memory no matter where it was dropped.
 */

/**
 * The card an incoming statement belongs to, if it is already known.
 *
 * Tried strongest first. The last four of the account number is the only field
 * that stays constant across statements; the credit limit changes, and the
 * display label changes with it whenever a field fails to parse.
 */
export function findHeldCard(
  cards: HeldCard[],
  meta: StatementMetadata,
  label: string
): HeldCard | undefined {
  if (meta.last4) {
    const byNumber = cards.find((c) => c.last4 === meta.last4);
    if (byNumber) return byNumber;
  }
  if (meta.cardName) {
    const byProduct = cards.find(
      (c) =>
        c.productName?.toLowerCase() === meta.cardName!.toLowerCase() &&
        (c.issuer ?? "").toLowerCase() === (meta.issuer ?? "").toLowerCase()
    );
    if (byProduct) return byProduct;
  }
  return cards.find((c) => c.name === label);
}

export interface IngestResult {
  meta: StatementMetadata;
  added: number;
  errors: number;
  fileName: string;
}

/** Parse files into the session. Returns what each file yielded. */
export function useStatementIngest() {
  const { session, addCard, updateCard, addTransactions } = useSession();
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState<string | null>(null);

  const ingest = useCallback(
    async (files: FileList | File[]): Promise<IngestResult[]> => {
      setBusy(true);
      setFailure(null);
      const results: IngestResult[] = [];
      try {
        for (const file of Array.from(files)) {
          const isPdf =
            file.type === "application/pdf" ||
            file.name.toLowerCase().endsWith(".pdf");

          // Metadata first: it decides the sign convention the row parser needs,
          // since a credit-card statement prints charges as positive.
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

          // The statement named the account — record it without asking, and
          // reuse the existing card when a later statement is for the same one.
          //
          // Matching on the display label alone split one card into several:
          // successive statements for the same account differ in credit limit
          // and, when the account-number line doesn't parse, in the label
          // itself. Identity comes from the account number when the statement
          // prints one, and from product + issuer otherwise.
          const label = statementLabel(meta);
          const existing = findHeldCard(session.heldCards, meta, label);
          const named = Boolean(meta.cardName || meta.issuer || meta.creditLimit);

          let sourceId: string | undefined;
          if (existing) {
            sourceId = existing.id;
            // Later statements carry the current limit and balance; earlier
            // ones must not overwrite them.
            const newer =
              !existing.statementThrough ||
              (meta.periodEnd ?? "") >= existing.statementThrough;
            if (newer) {
              updateCard(existing.id, {
                creditLimit: meta.creditLimit ?? existing.creditLimit,
                currentBalance: meta.currentBalance ?? existing.currentBalance,
                last4: meta.last4 ?? existing.last4,
                productName: meta.cardName ?? existing.productName,
                statementThrough: meta.periodEnd ?? existing.statementThrough,
              });
            }
          } else if (named) {
            sourceId = addCard({
              name: label,
              productName: meta.cardName,
              last4: meta.last4,
              statementThrough: meta.periodEnd,
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
              sourceId,
            })),
            {
              fileName: file.name,
              kind: isPdf ? "pdf" : "csv",
              added: rows.length,
              errors: errors.length,
            }
          );

          results.push({
            meta,
            added: rows.length,
            errors: errors.length,
            fileName: file.name,
          });
        }
      } catch {
        setFailure(
          "That file couldn't be read. CSV and text-based PDF statements work best."
        );
      } finally {
        setBusy(false);
      }
      return results;
    },
    [addCard, updateCard, addTransactions, session.heldCards]
  );

  return { ingest, busy, failure, setFailure };
}

export function StatementDropzone({
  onIngested,
  compact = false,
}: {
  onIngested?: (results: IngestResult[]) => void;
  /** Inline variant for pages that already have content above it. */
  compact?: boolean;
}) {
  const { ingest, busy, failure } = useStatementIngest();
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handle = useCallback(
    async (files: FileList | File[]) => {
      const results = await ingest(files);
      if (results.length) onIngested?.(results);
    },
    [ingest, onIngested]
  );

  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer.files?.length) void handle(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={
          "dashed-card cursor-pointer " +
          (compact ? "py-6" : "py-14") +
          (dragging ? " border-primary bg-accent text-card-foreground" : "")
        }
      >
        {busy ? (
          <>
            <Loader2 className={compact ? "h-4 w-4 animate-spin" : "h-6 w-6 animate-spin"} />
            <span className="text-sm">Reading your statement…</span>
          </>
        ) : (
          <>
            <Upload className={compact ? "h-4 w-4" : "h-6 w-6"} />
            <span className="text-sm font-medium">
              {compact
                ? "Drop a statement to add transactions"
                : "Drop a PDF or CSV statement, or click to choose"}
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
          onChange={(e) => e.target.files?.length && void handle(e.target.files)}
        />
      </div>

      {failure && (
        <p className="mt-3 flex items-start gap-2 border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 flex-shrink-0" />
          {failure}
        </p>
      )}
    </div>
  );
}

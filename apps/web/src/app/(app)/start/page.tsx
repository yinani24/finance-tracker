"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Check } from "lucide-react";
import { formatCurrency } from "@/lib/format";
import {
  StatementDropzone,
  type IngestResult,
} from "@/components/statement-dropzone";
import { statementLabel, statementUtilization } from "@/lib/statement/parse-metadata";

/**
 * Drop-and-go onboarding.
 *
 * A statement already names the card, the issuer, the credit limit and the
 * balance, so asking for them up front was friction we imposed for no reason.
 * Drop a file and everything below is derived. Nothing is uploaded — parsing
 * runs in this tab and the results live in session memory only.
 */
export default function StartPage() {
  const router = useRouter();
  const [detected, setDetected] = useState<IngestResult[]>([]);

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

      <StatementDropzone
        onIngested={(results) => setDetected((d) => [...d, ...results])}
      />

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

"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { createLinkToken, exchangePublicToken } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { Link2 } from "lucide-react";

export function PlaidLinkButton() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    createLinkToken()
      .then((res) => setLinkToken(res.link_token))
      .catch((err) => setError(err.message));
  }, []);

  const onSuccess = useCallback(
    async (publicToken: string, metadata: { institution?: { institution_id?: string; name?: string } | null }) => {
      setLoading(true);
      setError(null);
      try {
        await exchangePublicToken({
          public_token: publicToken,
          institution_id: metadata.institution?.institution_id,
          institution_name: metadata.institution?.name,
        });
        queryClient.invalidateQueries({ queryKey: ["plaid-items"] });
        queryClient.invalidateQueries({ queryKey: ["accounts"] });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to link account");
      } finally {
        setLoading(false);
      }
    },
    [queryClient]
  );

  const { open, ready } = usePlaidLink({
    token: linkToken,
    onSuccess,
  });

  return (
    <div>
      <button
        onClick={() => open()}
        disabled={!ready || loading}
        className="flex items-center gap-2 bg-green-600 text-white px-4 py-2.5 rounded-lg text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
      >
        <Link2 className="w-4 h-4" />
        {loading ? "Connecting..." : "Connect Bank Account"}
      </button>
      {error && (
        <p className="text-red-500 text-xs mt-2">{error}</p>
      )}
    </div>
  );
}

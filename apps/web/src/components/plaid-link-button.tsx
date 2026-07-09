"use client";

import { useCallback, useEffect, useState } from "react";
import { usePlaidLink } from "react-plaid-link";
import { createLinkToken, exchangePublicToken } from "@/lib/api";
import { useQueryClient } from "@tanstack/react-query";
import { Link2 } from "lucide-react";

// The link token must survive the OAuth redirect: OAuth banks (Chase, BofA, …)
// bounce the user to the bank and back to our redirect_uri, reloading this page.
// Re-initializing Link with a *new* token would start a different session and
// the OAuth handoff would fail, so we stash the original token and reuse it.
const OAUTH_TOKEN_KEY = "plaid_link_token";

export function PlaidLinkButton() {
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();

  // Plaid appends `?oauth_state_id=...` to redirect_uri when returning from an
  // OAuth bank. Its presence means we're completing an in-flight OAuth Link.
  const isOAuthRedirect =
    typeof window !== "undefined" &&
    window.location.search.includes("oauth_state_id=");

  useEffect(() => {
    if (isOAuthRedirect) {
      // Resume the OAuth flow with the token we started with.
      const stored = window.localStorage.getItem(OAUTH_TOKEN_KEY);
      if (stored) {
        setLinkToken(stored);
        return;
      }
      // No stored token (e.g. reload in a fresh tab) — fall through and mint a
      // new one; the user can retry from scratch.
    }
    createLinkToken()
      .then((res) => {
        setLinkToken(res.link_token);
        window.localStorage.setItem(OAUTH_TOKEN_KEY, res.link_token);
      })
      .catch((err) => setError(err.message));
  }, [isOAuthRedirect]);

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
        window.localStorage.removeItem(OAUTH_TOKEN_KEY);
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
    // On an OAuth return, hand Link the full callback URL so it can resume.
    receivedRedirectUri: isOAuthRedirect ? window.location.href : undefined,
  });

  // Completing an OAuth Link requires re-opening it automatically once ready —
  // the user already clicked "Connect" before being sent to their bank.
  useEffect(() => {
    if (isOAuthRedirect && ready) {
      open();
    }
  }, [isOAuthRedirect, ready, open]);

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

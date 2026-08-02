"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { refreshRecommendations } from "@/lib/api";

/**
 * Recomputes the recommendation family on the server and invalidates every
 * query under the `["recommendations"]` key.
 *
 * The three surfaces it feeds — next card, portfolio, spending profile — used
 * to be inner tabs of a single page that owned this button. They are now
 * sibling routes, so the button is shared rather than duplicated. The mutation
 * and the invalidation key are unchanged.
 */
export function RefreshRecommendationsButton() {
  const queryClient = useQueryClient();

  const refreshMutation = useMutation({
    mutationFn: refreshRecommendations,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  return (
    <div className="flex items-center justify-end mb-6">
      <button
        onClick={() => refreshMutation.mutate()}
        disabled={refreshMutation.isPending}
        className="flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-border hover:bg-accent/50 motion-base disabled:opacity-50"
      >
        <RefreshCw
          className={`w-4 h-4 ${refreshMutation.isPending ? "animate-spin" : ""}`}
        />
        Refresh
      </button>
    </div>
  );
}

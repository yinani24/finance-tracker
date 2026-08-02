"use client";

import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";

/**
 * Drives the browser's View Transitions API for in-app navigation.
 *
 * Next's `experimental.viewTransition` flag only *enables* React's
 * ViewTransition support — it does not wrap navigations, and stable React
 * 19.2 does not export `unstable_ViewTransition`. Left alone, nothing ever
 * calls `startViewTransition`, which is why route changes had no transition at
 * all despite the flag and the `::view-transition-*` CSS both being in place.
 *
 * So we call it ourselves. The subtlety is that `startViewTransition` wants a
 * callback that updates the DOM, but `router.push` is asynchronous: the new
 * route renders some frames later. We therefore hand the browser a promise and
 * resolve it once `usePathname` reports the new route, which is the point at
 * which the incoming DOM exists and can be captured.
 *
 * A capture-phase click listener is used rather than a custom Link so every
 * internal navigation is covered — sidebar items, panel cards, inline links —
 * without touching call sites.
 */
export function ViewTransitions() {
  const router = useRouter();
  const pathname = usePathname();
  const resolveRef = useRef<(() => void) | null>(null);
  const timerRef = useRef<number | null>(null);

  // The route has rendered — let the browser capture the new state.
  useEffect(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    resolveRef.current?.();
    resolveRef.current = null;
  }, [pathname]);

  useEffect(() => {
    function onClick(event: MouseEvent) {
      // Respect every way a user asks for "not a normal in-page navigation".
      if (
        event.defaultPrevented ||
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      const anchor = (event.target as Element | null)?.closest?.("a");
      if (!anchor) return;

      const href = anchor.getAttribute("href");
      if (
        !href ||
        anchor.hasAttribute("download") ||
        (anchor.getAttribute("target") ?? "") === "_blank" ||
        !href.startsWith("/") // external, hash, mailto: — leave alone
      ) {
        return;
      }

      const url = new URL(href, window.location.href);
      if (url.pathname === window.location.pathname) return; // same route
      if (typeof document.startViewTransition !== "function") return; // let Next handle it

      event.preventDefault();
      document.startViewTransition(
        () =>
          new Promise<void>((resolve) => {
            resolveRef.current = resolve;
            // Safety valve: never leave the page frozen under the transition
            // pseudo-elements if a navigation stalls or is cancelled.
            timerRef.current = window.setTimeout(() => {
              resolveRef.current = null;
              resolve();
            }, 1200);
            router.push(url.pathname + url.search);
          })
      );
    }

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [router]);

  return null;
}

import { useSyncExternalStore } from "react";

// Always returns the same unsubscribe; the value never changes after mount, so
// there is nothing to subscribe to.
const emptySubscribe = () => () => {};

/**
 * `false` during SSR and the first (hydrating) client render, `true` immediately
 * afterwards.
 *
 * This is the React-idiomatic replacement for the `useState(false)` +
 * `useEffect(() => setMounted(true), [])` mount flag: reading through
 * `useSyncExternalStore` avoids the synchronous `setState`-in-effect (which
 * `react-hooks/set-state-in-effect` flags as a cascading render) while staying
 * hydration-safe — React uses the server snapshot (`false`) to hydrate, then the
 * client snapshot (`true`) on the next render, so the markup never mismatches.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false
  );
}

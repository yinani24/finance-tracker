"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

/**
 * Presentational wrapper that replays a short enter animation whenever the
 * route changes.
 *
 * The animation is restarted by removing and re-adding the class rather than
 * by keying the element on the pathname: keying would remount `children` on
 * every navigation, which is a behavioural change we explicitly do not want.
 * Toggling the class touches nothing but the DOM node's class list.
 *
 * Reduced-motion users get no animation at all — see `.page-enter` in
 * globals.css, where the `prefers-reduced-motion` block disables it.
 */
export function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.classList.remove("page-enter");
    // Reading a layout property flushes the removal so re-adding the class
    // restarts the animation instead of being coalesced into a no-op.
    void el.offsetWidth;
    el.classList.add("page-enter");
  }, [pathname]);

  return (
    <div ref={ref} className="page-enter">
      {children}
    </div>
  );
}

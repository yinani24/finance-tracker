"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Compass, Lightbulb, Wallet } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

// Three surfaces, one level of tabs. Explore browses the whole card dataset,
// Recommendations ranks what to get next, and Portfolio is the cards you
// actually hold and how well they fit your spending. "Your cards" folded into
// Portfolio — holding a card and judging it are the same question.
const TABS = [
  { href: "/cards/explore", label: "Explore", icon: Compass, exact: false },
  {
    href: "/cards/recommendations",
    label: "Recommendations",
    icon: Lightbulb,
    exact: false,
  },
  { href: "/cards/portfolio", label: "Portfolio", icon: Wallet, exact: false },
] as const;

// Module-level so the measurement callback below depends on nothing but the
// pathname, keeping its dependency list genuinely exhaustive.
function isActive(pathname: string, href: string, exact: boolean): boolean {
  return exact ? pathname === href : pathname.startsWith(href);
}

export default function CardsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  // Geometry of the sliding active pill. Purely presentational: the tabs are
  // still plain links and navigation is unchanged.
  //
  // The measured position is written straight to the indicator's style rather
  // than held in React state. The pill is a visual artefact of the DOM's own
  // layout, so this keeps it out of the render cycle entirely — no extra render
  // per navigation, and no setState-inside-an-effect.
  const stripRef = useRef<HTMLDivElement>(null);
  const indicatorRef = useRef<HTMLSpanElement>(null);
  const tabRefs = useRef(new Map<string, HTMLAnchorElement>());

  const measure = useCallback(() => {
    const indicator = indicatorRef.current;
    if (!indicator) return;
    const activeHref = TABS.find((t) =>
      isActive(pathname, t.href, t.exact)
    )?.href;
    const el = activeHref ? tabRefs.current.get(activeHref) : undefined;
    if (!el) {
      indicator.dataset.ready = "false";
      return;
    }
    indicator.style.left = `${el.offsetLeft}px`;
    indicator.style.width = `${el.offsetWidth}px`;

    if (indicator.dataset.ready !== "true") {
      // While `data-ready` is false the indicator has `transition: none`, so
      // flushing layout here commits the initial position un-animated. Only
      // then do we enable transitions, and subsequent tab changes slide.
      void indicator.offsetWidth;
      indicator.dataset.ready = "true";
    }
  }, [pathname]);

  useEffect(() => {
    measure();
  }, [measure]);

  // Re-measure when the strip resizes (font loading, window resize, zoom).
  useEffect(() => {
    const strip = stripRef.current;
    if (!strip || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => measure());
    observer.observe(strip);
    return () => observer.disconnect();
  }, [measure]);

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-card-foreground">Cards</h1>
        <p className="text-sm text-muted mt-1">
          Manage your credit cards, explore new ones, and get personalized
          recommendations
        </p>
      </div>

      <div
        ref={stripRef}
        className="segmented flex gap-1 mb-8 bg-accent/60 rounded-full p-1 w-fit max-w-full overflow-x-auto"
      >
        <span
          ref={indicatorRef}
          aria-hidden="true"
          className="segmented-indicator"
          data-ready="false"
        />
        {TABS.map(({ href, label, icon: Icon, exact }) => {
          const active = isActive(pathname, href, exact);
          return (
            <Link
              key={href}
              href={href}
              ref={(node) => {
                if (node) tabRefs.current.set(href, node);
                else tabRefs.current.delete(href);
              }}
              data-active={active}
              aria-current={active ? "page" : undefined}
              className={cn(
                "segmented-item flex shrink-0 items-center gap-2 px-4 py-2 text-sm rounded-full whitespace-nowrap",
                active
                  ? "text-card-foreground"
                  : "text-muted hover:text-card-foreground"
              )}
            >
              <Icon
                className={cn("w-4 h-4 motion-fade", active ? "opacity-100" : "opacity-70")}
              />
              {label}
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}

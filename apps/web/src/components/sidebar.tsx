"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  House,
  Wallet,
  Receipt,
  PieChart,
  WalletCards,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Sparkles,
  ArrowUpRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";

// Spending profile is a destination in its own right, not a tab buried under
// Cards: it is the analysis the card advice is derived from, and it is what the
// user reads on its own. Goals were removed — nothing in the statement-driven
// flow fed them. Accounts became Income, the other half of the picture that a
// card statement can't show.
const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: House, section: "Overview" },
  { href: "/transactions", label: "Transactions", icon: Receipt, section: "Overview" },
  { href: "/income", label: "Income", icon: Wallet, section: "Overview" },
  {
    href: "/spending-profile",
    label: "Spending profile",
    icon: PieChart,
    section: "Optimize",
  },
  { href: "/cards", label: "Cards", icon: WalletCards, section: "Optimize" },
];



export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);


  useEffect(() => {
    const saved = localStorage.getItem("sidebar-collapsed");
    if (saved === "true") setCollapsed(true);
  }, []);

  function toggle() {
    setCollapsed((prev) => {
      localStorage.setItem("sidebar-collapsed", String(!prev));
      return !prev;
    });
  }


  return (
    <aside
      className={cn(
        "group/sidebar relative border-r border-border bg-card flex flex-col h-screen sticky top-0 transition-[width] duration-[var(--dur-page)] ease-[var(--ease-composio)] overflow-hidden",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div
        className={cn(
          "border-b border-border flex items-center",
          collapsed ? "p-3 justify-center" : "p-6 justify-between"
        )}
      >
        <div className={cn("flex items-center", collapsed ? "" : "gap-3")}>
          <button
            onClick={collapsed ? toggle : undefined}
            className={cn(
              "flex-shrink-0 w-8 h-8 rounded-lg bg-primary flex items-center justify-center motion-base",
              collapsed && "cursor-pointer hover:scale-105 active:scale-95"
            )}
            title={collapsed ? "Expand sidebar" : undefined}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 18 18"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
              className="text-primary-foreground"
            >
              <path
                d="M3 4.5C3 3.67 3.67 3 4.5 3H13.5C14.33 3 15 3.67 15 4.5V6H3V4.5Z"
                fill="currentColor"
                opacity="0.5"
              />
              <path
                d="M3 6H15V13.5C15 14.33 14.33 15 13.5 15H4.5C3.67 15 3 14.33 3 13.5V6Z"
                fill="currentColor"
              />
              <path
                d="M6 9.5H10"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                className="text-primary"
              />
              <path
                d="M6 12H8.5"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                className="text-primary"
              />
            </svg>
          </button>
          {!collapsed && (
            <h1 className="text-lg font-bold text-card-foreground truncate font-heading">
              Finance Tracker
            </h1>
          )}
        </div>
        {!collapsed && (
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={toggle}
            title="Collapse sidebar"
          >
            <PanelLeftClose className="w-4 h-4" />
          </Button>
        )}
      </div>

      {/* Search affordance — mirrors the dashboard-app convention of a
          command-palette row pinned above the nav. */}
      <div className="pt-2">
        <button
          type="button"
          title="Search"
          className={cn(
            "w-full flex items-center text-sm text-muted",
            "motion-base hover:bg-accent/50 hover:text-card-foreground",
            collapsed ? "justify-center p-2.5" : "gap-3 px-4 py-2.5"
          )}
        >
          <Search className="w-[18px] h-[18px] flex-shrink-0" strokeWidth={1.75} />
          {!collapsed && (
            <>
              <span className="truncate">Search</span>
              <kbd className="ml-auto rounded border border-border px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                ⌘K
              </kbd>
            </>
          )}
        </button>
      </div>

      <nav className="flex-1 py-2 space-y-0.5">
        {navItems.map(({ href, label, icon: Icon, section }, i) => {
          const active = pathname.startsWith(href);
          // Start a labelled group whenever the section changes, so the nav
          // reads as grouped areas rather than one flat list.
          const prev = i > 0 ? navItems[i - 1].section : undefined;
          const startsSection = section !== prev;
          return (
            <div key={href}>
              {startsSection &&
                (section ? (
                  !collapsed && (
                    <div className="px-4 pb-1 pt-3 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                      {section}
                    </div>
                  )
                ) : (
                  <div className="my-2 border-t border-border" />
                ))}
              <Link
                href={href}
                title={collapsed ? label : undefined}
                data-active={active}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "nav-item flex items-center text-sm font-medium",
                  collapsed ? "justify-center p-2.5" : "gap-3 px-4 py-2.5",
                  active
                    ? "text-sidebar-accent-foreground"
                    : "text-muted hover:text-card-foreground"
                )}
              >
                <Icon className="nav-icon w-[18px] h-[18px] flex-shrink-0" strokeWidth={1.75} />
                {!collapsed && <span className="truncate">{label}</span>}
              </Link>
            </div>
          );
        })}
      </nav>

      {/* Contextual callout pinned above the account block, as in the
          reference's promo slot. */}
      {!collapsed && (
        <Link
          href="/transactions"
          className="mx-3 mb-2 block rounded-lg border border-primary/25 bg-primary/10 p-3 motion-base hover:bg-primary/15"
        >
          <span className="mb-1 flex items-center gap-1.5 text-[13px] font-medium text-card-foreground">
            <Sparkles className="h-3.5 w-3.5 text-link" />
            Import a statement
            <ArrowUpRight className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
          </span>
          <span className="block text-xs leading-relaxed text-muted">
            Add a CSV or PDF to sharpen your card recommendations.
          </span>
        </Link>
      )}

    </aside>
  );
}

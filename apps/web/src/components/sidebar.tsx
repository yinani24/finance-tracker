"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Wallet,
  ArrowLeftRight,
  Target,
  CreditCard,
  Settings,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { useQuery } from "@tanstack/react-query";
import { getMe } from "@/lib/api";
import { useState, useEffect } from "react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { Button } from "@/components/ui/button";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, section: "Overview" },
  { href: "/accounts", label: "Accounts", icon: Wallet, section: "Overview" },
  { href: "/transactions", label: "Transactions", icon: ArrowLeftRight, section: "Overview" },
  { href: "/cards", label: "Cards", icon: CreditCard, section: "Optimize" },
  { href: "/goals", label: "Goals", icon: Target, section: "Optimize" },
  { href: "/settings", label: "Settings", icon: Settings, section: null },
];

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

function getDisplayName(user: { user_metadata?: Record<string, unknown>; email?: string | null }): string {
  return (user.user_metadata?.full_name as string) ??
    user.email?.split("@")[0] ??
    "User";
}

export function Sidebar() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();
  const [collapsed, setCollapsed] = useState(false);

  const { data: appUser } = useQuery({
    queryKey: ["me"],
    queryFn: getMe,
    enabled: !!user,
  });

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

  const displayName = appUser?.full_name || (user ? getDisplayName(user) : "");
  const initials = user ? getInitials(displayName) : "";

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
      <div className="px-2 pt-2">
        <button
          type="button"
          title="Search"
          className={cn(
            "w-full flex items-center rounded-lg text-sm text-muted",
            "motion-base hover:bg-accent/50 hover:text-card-foreground",
            collapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5"
          )}
        >
          <Search className="w-5 h-5 flex-shrink-0" />
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

      <nav className="flex-1 p-2 space-y-1">
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
                    <div className="px-3 pb-1 pt-3 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
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
                  "nav-item flex items-center rounded-lg text-sm font-medium",
                  collapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5",
                  active
                    ? "text-sidebar-accent-foreground"
                    : "text-muted hover:text-card-foreground"
                )}
              >
                <Icon className="nav-icon w-5 h-5 flex-shrink-0" />
                {!collapsed && <span className="truncate">{label}</span>}
              </Link>
            </div>
          );
        })}
      </nav>

      <div className="p-2 border-t border-border">
        {user && (
          <Popover>
            <PopoverTrigger
              className={cn(
                "w-full flex items-center rounded-lg motion-base hover:bg-accent/50 cursor-pointer",
                collapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5"
              )}
            >
              <Avatar size="sm">
                <AvatarFallback className="text-[10px] font-semibold">
                  {initials}
                </AvatarFallback>
              </Avatar>
              {!collapsed && (
                <div className="min-w-0 text-left">
                  <div className="text-sm font-medium text-card-foreground truncate">
                    {displayName}
                  </div>
                  <div className="text-xs text-muted-foreground truncate">
                    {user.email}
                  </div>
                </div>
              )}
            </PopoverTrigger>
            <PopoverContent side="top" align="start" sideOffset={8} className="w-56 p-1">
              <div className="px-3 py-2">
                <p className="text-sm font-medium truncate">{displayName}</p>
                <p className="text-xs text-muted-foreground truncate">{user.email}</p>
              </div>
              <Separator />
              <Link
                href="/settings"
                className="flex items-center gap-2 rounded-md px-3 py-2 text-sm text-popover-foreground hover:bg-accent motion-base"
              >
                <Settings className="w-4 h-4" />
                Settings
              </Link>
              <Separator />
              <button
                onClick={signOut}
                className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-destructive hover:bg-destructive/10 motion-base"
              >
                <LogOut className="w-4 h-4" />
                Sign out
              </button>
            </PopoverContent>
          </Popover>
        )}
      </div>
    </aside>
  );
}

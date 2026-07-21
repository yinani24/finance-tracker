"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { CreditCard, Compass, Lightbulb } from "lucide-react";
import { cn } from "@/lib/utils";

// Card-related surfaces are consolidated under a single "Cards" section with
// internal tabs. "Your cards" is the index route (/cards); the others are nested
// segments so each keeps its own page component and data fetching.
const TABS = [
  { href: "/cards", label: "Your cards", icon: CreditCard, exact: true },
  { href: "/cards/explore", label: "Explore", icon: Compass, exact: false },
  {
    href: "/cards/recommendations",
    label: "Recommendations",
    icon: Lightbulb,
    exact: false,
  },
] as const;

export default function CardsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-card-foreground">Cards</h1>
        <p className="text-sm text-muted mt-1">
          Manage your credit cards, explore new ones, and get personalized
          recommendations
        </p>
      </div>

      <div className="flex gap-1 mb-8 bg-muted/30 rounded-lg p-1 w-fit">
        {TABS.map(({ href, label, icon: Icon, exact }) => {
          const active = exact
            ? pathname === href
            : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-2 px-4 py-2 text-sm rounded-md transition-colors",
                active
                  ? "bg-card text-card-foreground shadow-sm"
                  : "text-muted hover:text-card-foreground"
              )}
            >
              <Icon className="w-4 h-4" />
              {label}
            </Link>
          );
        })}
      </div>

      {children}
    </div>
  );
}

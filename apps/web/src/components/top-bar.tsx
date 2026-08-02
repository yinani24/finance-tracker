"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";
import { useHydrated } from "@/lib/use-hydrated";

export function TopBar() {
  const { setTheme, resolvedTheme } = useTheme();
  // The theme toggle depends on the resolved (client-only) theme, so it must not
  // render until the client has hydrated — otherwise the icon flashes/mismatches.
  const mounted = useHydrated();

  function toggleTheme() {
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  }

  return (
    <header className="h-12 border-b border-border bg-card flex items-center justify-end px-6">
      {mounted && (
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={toggleTheme}
          title={resolvedTheme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        >
          {resolvedTheme === "dark" ? (
            <Sun className="w-4 h-4" />
          ) : (
            <Moon className="w-4 h-4" />
          )}
        </Button>
      )}
    </header>
  );
}

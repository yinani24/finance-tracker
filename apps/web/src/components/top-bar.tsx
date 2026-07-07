"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

export function TopBar() {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

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

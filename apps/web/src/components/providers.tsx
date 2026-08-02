"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "next-themes";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { staleTime: 30_000, retry: 1 },
        },
      })
  );

  return (
    /*
     * Dark is the product's default look. `enableSystem` stays on so the
     * Settings "System" option keeps working and light remains fully
     * switchable — it only means "system" is *selectable*, not that it is the
     * fallback; that is what `defaultTheme` decides. `disableTransitionOnChange`
     * stops the motion system from cross-fading every token on a theme flip.
     */
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem
      disableTransitionOnChange
    >
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ThemeProvider>
  );
}

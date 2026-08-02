import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AuthProvider } from "@/lib/auth-context";

// Inter for UI text and JetBrains Mono for figures/codes — the same pairing
// the reference dashboard uses (its mono is JetBrains Mono outright).
const sans = Inter({
  variable: "--font-geist-sans",
  subsets: ["latin"],
  display: "swap",
});

const mono = JetBrains_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Finance Tracker",
  description: "Personal finance tracker and analytics dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    /*
     * `dark` is the server-rendered default so the very first paint is already
     * dark; next-themes' pre-hydration script replaces it with a stored `light`
     * preference before anything is painted, so neither theme flashes.
     */
    <html
      lang="en"
      suppressHydrationWarning
      className={`dark ${sans.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="h-full flex overflow-hidden">
        <Providers>
          <AuthProvider>{children}</AuthProvider>
        </Providers>
      </body>
    </html>
  );
}

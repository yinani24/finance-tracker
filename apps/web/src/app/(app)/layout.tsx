import { Sidebar } from "@/components/sidebar";
import { TopBar } from "@/components/top-bar";
import { PageTransition } from "@/components/page-transition";
import { ViewTransitions } from "@/components/view-transitions";

// Single-user app: no login gate. The shell renders directly.
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <ViewTransitions />
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 h-screen">
        <TopBar />
        <main className="flex-1 overflow-y-auto">
          <PageTransition>{children}</PageTransition>
        </main>
      </div>
    </>
  );
}

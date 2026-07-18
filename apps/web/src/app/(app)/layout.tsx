import { Sidebar } from "@/components/sidebar";
import { TopBar } from "@/components/top-bar";

// Single-user app: no login gate. The shell renders directly.
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <>
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 h-screen">
        <TopBar />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </>
  );
}

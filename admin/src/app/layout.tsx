import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth-context";
import { AdminGate } from "@/components/admin-gate";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kajian App Admin",
  description: "Admin dashboard for Kajian App",
};

// Every page here needs live Firebase auth state + a live backend-core
// call — nothing is meaningfully static. Without this, Next.js tries to
// prerender pages at build time, which fails because Firebase can't
// initialize without real runtime env vars (NEXT_PUBLIC_FIREBASE_*).
export const dynamic = "force-dynamic";

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <AdminGate>{children}</AdminGate>
        </AuthProvider>
      </body>
    </html>
  );
}

"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth-context";

export function NavBar() {
  const { firebaseUser, signOutUser } = useAuth();

  return (
    <div className="nav">
      <div className="nav-links">
        <strong style={{ color: "var(--text)" }}>Kajian App Admin</strong>
        <Link href="/">Dashboard</Link>
        <Link href="/users">Users</Link>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ color: "var(--text-muted)", fontSize: 13 }}>
          {firebaseUser?.email}
        </span>
        <button
          className="button"
          style={{ background: "var(--surface-2)" }}
          onClick={signOutUser}
        >
          Sign out
        </button>
      </div>
    </div>
  );
}

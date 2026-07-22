"use client";

import type { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { NavBar } from "./nav-bar";

/// Gates all admin pages behind: signed in (Firebase) AND is_admin=true
/// (backend-core). Neither the app nor this dashboard can self-grant
/// admin access — see backend-core/scripts/promote_admin.py.
export function AdminGate({ children }: { children: ReactNode }) {
  const { firebaseUser, me, loading, error, signIn } = useAuth();

  if (loading) {
    return <div className="center-screen">Loading…</div>;
  }

  if (!firebaseUser) {
    return (
      <div className="center-screen">
        <div className="card" style={{ textAlign: "center", minWidth: 320 }}>
          <h1 style={{ marginTop: 0 }}>Kajian App Admin</h1>
          <p style={{ color: "var(--text-muted)" }}>
            Sign in with the Google account tied to your admin user.
          </p>
          <button className="button" onClick={signIn}>
            Sign in with Google
          </button>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="center-screen">
        <div className="card" style={{ textAlign: "center", maxWidth: 420 }}>
          <p className="error-text">{error}</p>
          <p style={{ color: "var(--text-muted)", fontSize: 14 }}>
            Signed in as {firebaseUser.email}. Make sure this account has
            signed into the Kajian App at least once, then grant admin
            access via <code>backend-core/scripts/promote_admin.py</code>.
          </p>
        </div>
      </div>
    );
  }

  if (!me?.isAdmin) {
    return (
      <div className="center-screen">
        <div className="card" style={{ textAlign: "center" }}>
          <p>
            Signed in as {firebaseUser.email}, but this account isn&apos;t
            an admin.
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <NavBar />
      <div className="container">{children}</div>
    </>
  );
}

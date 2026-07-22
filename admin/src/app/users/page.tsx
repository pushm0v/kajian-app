"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ApiError, type UserSummaryOut } from "@/lib/api";

export default function UsersPage() {
  const [users, setUsers] = useState<UserSummaryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .users()
      .then(setUsers)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!users) return <p>Loading…</p>;

  return (
    <div>
      <h1>Users</h1>
      <div className="card">
        <table>
          <thead>
            <tr>
              <th>User</th>
              <th>Sessions</th>
              <th>Admin</th>
              <th>Joined</th>
              <th>Last seen</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td>
                  <Link href={`/users/${u.id}`}>
                    {u.displayName ?? u.email ?? u.id}
                  </Link>
                  {u.displayName && u.email ? (
                    <div style={{ color: "var(--text-muted)", fontSize: 12 }}>
                      {u.email}
                    </div>
                  ) : null}
                </td>
                <td>{u.sessionCount}</td>
                <td>{u.isAdmin ? <span className="badge completed">admin</span> : "—"}</td>
                <td>{new Date(u.createdAt).toLocaleDateString()}</td>
                <td>{new Date(u.lastSeenAt).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

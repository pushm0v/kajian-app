"use client";

import { useEffect, useState } from "react";
import { api, ApiError, type StatsOut } from "@/lib/api";

function formatDuration(ms: number): string {
  const hours = Math.floor(ms / 3_600_000);
  const minutes = Math.floor((ms % 3_600_000) / 60_000);
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export default function DashboardPage() {
  const [stats, setStats] = useState<StatsOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .stats()
      .then(setStats)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, []);

  if (error) return <p className="error-text">{error}</p>;
  if (!stats) return <p>Loading…</p>;

  return (
    <div>
      <h1>Dashboard</h1>
      <div className="stat-grid">
        <div className="card">
          <div className="stat-value">{stats.userCount}</div>
          <div className="stat-label">Users</div>
        </div>
        <div className="card">
          <div className="stat-value">{stats.sessionCount}</div>
          <div className="stat-label">Kajian sessions</div>
        </div>
        <div className="card">
          <div className="stat-value">{stats.completedSessionCount}</div>
          <div className="stat-label">Fully processed</div>
        </div>
        <div className="card">
          <div className="stat-value">
            {formatDuration(stats.totalAudioDurationMs)}
          </div>
          <div className="stat-label">Total audio recorded</div>
        </div>
      </div>
    </div>
  );
}

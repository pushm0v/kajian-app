"use client";

import { use, useEffect, useState } from "react";
import { api, ApiError, type KajianSessionOut } from "@/lib/api";

function formatDuration(ms: number): string {
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.floor((ms % 60_000) / 1000);
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function SessionRow({ session }: { session: KajianSessionOut }) {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  async function loadAudio() {
    try {
      const { downloadUrl } = await api.sessionAudioUrl(session.id);
      setAudioUrl(downloadUrl);
    } catch (e) {
      setAudioError(e instanceof ApiError ? e.message : String(e));
    }
  }

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
        }}
        onClick={() => setExpanded((v) => !v)}
      >
        <div>
          <strong>{session.title}</strong>
          <div style={{ color: "var(--text-muted)", fontSize: 13 }}>
            {session.speaker ? `${session.speaker} · ` : ""}
            {new Date(session.createdAt).toLocaleString()} ·{" "}
            {formatDuration(session.durationMs)}
          </div>
        </div>
        <span className={`badge ${session.status}`}>{session.status}</span>
      </div>

      {expanded && (
        <div style={{ marginTop: 16, borderTop: "1px solid var(--border)", paddingTop: 16 }}>
          {session.hasAudio && (
            <div style={{ marginBottom: 16 }}>
              {audioUrl ? (
                <audio controls src={audioUrl} style={{ width: "100%" }} />
              ) : (
                <button className="button" onClick={loadAudio}>
                  Load audio
                </button>
              )}
              {audioError && <p className="error-text">{audioError}</p>}
            </div>
          )}

          {session.note && (
            <div style={{ marginBottom: 16 }}>
              <h4 style={{ marginBottom: 4 }}>Summary</h4>
              <p style={{ color: "var(--text-muted)" }}>{session.note.summary}</p>
              {session.note.keyPoints.length > 0 && (
                <ul>
                  {session.note.keyPoints.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {session.transcript.length > 0 && (
            <div>
              <h4 style={{ marginBottom: 4 }}>Transcript</h4>
              <div style={{ maxHeight: 240, overflowY: "auto", fontSize: 14 }}>
                {session.transcript.map((seg) => (
                  <p key={seg.id} style={{ margin: "4px 0" }}>
                    <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                      [{formatDuration(seg.startMs)}]
                    </span>{" "}
                    {seg.text}
                  </p>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function UserSessionsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [sessions, setSessions] = useState<KajianSessionOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .userSessions(id)
      .then(setSessions)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [id]);

  if (error) return <p className="error-text">{error}</p>;
  if (!sessions) return <p>Loading…</p>;

  return (
    <div>
      <h1>Sessions</h1>
      {sessions.length === 0 ? (
        <p style={{ color: "var(--text-muted)" }}>No sessions yet.</p>
      ) : (
        sessions.map((s) => <SessionRow key={s.id} session={s} />)
      )}
    </div>
  );
}

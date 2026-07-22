// Client for backend-core's /admin/* and /me routes. Every request carries
// the signed-in Firebase user's ID token as a bearer token — backend-core
// verifies it and checks the mapped user's is_admin flag (see
// ../../../backend-core/app/auth.py's current_admin dependency). A 403
// here means the signed-in account isn't an admin — see
// backend-core/scripts/promote_admin.py to grant access.

import { auth } from "./firebase";

const BASE_URL = process.env.NEXT_PUBLIC_CORE_API_URL ?? "";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (!user) throw new ApiError(401, "Not signed in");
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}` };
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: await authHeader(),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  return res.json();
}

export interface MeOut {
  id: string;
  email: string | null;
  displayName: string | null;
  photoUrl: string | null;
  isAdmin: boolean;
  createdAt: string;
}

export interface StatsOut {
  userCount: number;
  sessionCount: number;
  completedSessionCount: number;
  totalAudioDurationMs: number;
}

export interface UserSummaryOut {
  id: string;
  email: string | null;
  displayName: string | null;
  photoUrl: string | null;
  isAdmin: boolean;
  createdAt: string;
  lastSeenAt: string;
  sessionCount: number;
}

export interface TranscriptSegmentOut {
  id: string;
  text: string;
  startMs: number;
  endMs: number;
  speaker: string | null;
  isFinal: boolean;
}

export interface ScriptureReferenceOut {
  type: string;
  citation: string;
  note: string | null;
}

export interface KajianNoteOut {
  summary: string;
  keyPoints: string[];
  topics: string[];
  references: ScriptureReferenceOut[];
  actionItems: string[];
  generatedAt: string;
}

export interface KajianSessionOut {
  id: string;
  title: string;
  speaker: string | null;
  location: string | null;
  createdAt: string;
  durationMs: number;
  localeId: string;
  status: string;
  transcript: TranscriptSegmentOut[];
  note: KajianNoteOut | null;
  hasAudio: boolean;
}

export const api = {
  me: () => get<MeOut>("/me"),
  stats: () => get<StatsOut>("/admin/stats"),
  users: () => get<UserSummaryOut[]>("/admin/users"),
  userSessions: (userId: string) =>
    get<KajianSessionOut[]>(`/admin/users/${userId}/sessions`),
  sessionAudioUrl: (sessionId: string) =>
    get<{ downloadUrl: string }>(`/admin/sessions/${sessionId}/audio-url`),
};

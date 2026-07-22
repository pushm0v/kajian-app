# Kajian App Admin Dashboard

A small Next.js admin dashboard for backend-core (`../backend-core/`) —
user list, per-user session browsing with audio playback and transcript
viewing, and basic usage stats.

Authenticates the same way the mobile app does — Firebase Auth (Google
sign-in) — but as a separate Web app registration in the same Firebase
project, verified server-side by backend-core against a user's `is_admin`
flag (see `../backend-core/app/auth.py`'s `current_admin` dependency and
`../backend-core/scripts/promote_admin.py` for granting access).

## Firebase Web app setup

The Flutter app only has iOS/Android registered in Firebase so far — you
need to register a new **Web** app in the same project for this dashboard
to sign in with:

1. [Firebase console](https://console.firebase.google.com/) → your project
   (`aplikasi-raya`) → ⚙️ Project Settings → scroll to "Your apps" → **Add
   app** → Web (`</>`  icon).
2. Give it any nickname (e.g. "Kajian Admin"). You don't need Firebase
   Hosting.
3. Copy the `apiKey`, `authDomain`, and `appId` values from the config
   snippet shown — these go into `.env.local` (see below).
4. Google sign-in must already be enabled as a provider (Authentication →
   Sign-in method) — it should be, since the mobile app uses it.
5. Add `http://localhost:3000` (dev) and your deployed admin URL to
   Authentication → Settings → **Authorized domains**, or Google sign-in's
   popup will fail with an unauthorized-domain error.

## Setup

```bash
cd admin
cp .env.example .env.local
# fill in NEXT_PUBLIC_FIREBASE_* from the Firebase console step above,
# and NEXT_PUBLIC_CORE_API_URL to point at your backend-core deployment

npm install
npm run dev
```

Open http://localhost:3000, sign in with Google, and you should land on
the dashboard — assuming your account already has `is_admin=true` (see
below).

## Granting yourself admin access

Sign into the **Flutter app** at least once first (this auto-provisions
your `User` row in backend-core), then run, on the backend-core host:

```bash
docker compose exec kajian-core-api python scripts/promote_admin.py you@example.com
```

## Deploying

This is a standard Next.js app — `npm run build && npm run start`, or
deploy to any Node.js host / Vercel / your homelab via Docker. Set the
same env vars from `.env.example` as real environment variables in
production rather than `.env.local`.

No Dockerfile is included here (unlike `backend/`, `backend-whisper/`,
`backend-core/`) since Next.js admin dashboards are commonly deployed to
a platform like Vercel rather than self-hosted in a container — add one
if you'd rather run this alongside the other services on your homelab.

## Notes

- All pages are forced dynamic (`export const dynamic = "force-dynamic"`
  in `src/app/layout.tsx`) — nothing here is meaningfully static, since
  every page needs live Firebase auth state and a live backend-core call.
  Without this, `next build` tries to prerender pages and fails because
  Firebase can't initialize without real runtime env vars.
- Styling is plain CSS (`src/app/globals.css`), no framework — this is a
  small internal tool, not worth a design system.

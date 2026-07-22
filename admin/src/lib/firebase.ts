// Firebase Web SDK setup for the admin dashboard.
//
// This is a SEPARATE Firebase Web app registration from the Flutter app's
// iOS/Android ones (see ../../lib/firebase_options.dart) — same Firebase
// PROJECT (aplikasi-raya), but you need to register a new Web app in the
// Firebase console (Project Settings > Add app > Web) to get the config
// values below, since none existed yet when this was written. See
// ../../README.md's "Firebase Web app setup" section for exact steps.
import { initializeApp, getApps, type FirebaseOptions } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig: FirebaseOptions = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

// Next.js re-evaluates this module on every hot-reload in dev — guard
// against re-initializing an already-registered app.
export const firebaseApp =
  getApps()[0] ?? initializeApp(firebaseConfig);

export const auth = getAuth(firebaseApp);
export const googleProvider = new GoogleAuthProvider();

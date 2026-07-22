"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";
import { auth, googleProvider } from "./firebase";
import { api, ApiError, type MeOut } from "./api";

interface AuthContextValue {
  firebaseUser: User | null;
  me: MeOut | null;
  loading: boolean;
  error: string | null;
  signIn: () => Promise<void>;
  signOutUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [firebaseUser, setFirebaseUser] = useState<User | null>(null);
  const [me, setMe] = useState<MeOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return onAuthStateChanged(auth, async (user) => {
      setFirebaseUser(user);
      setError(null);
      if (user == null) {
        setMe(null);
        setLoading(false);
        return;
      }
      try {
        setMe(await api.me());
      } catch (e) {
        // A signed-in Firebase user who isn't provisioned/admin in
        // backend-core yet — surfaced in the UI rather than silently
        // stuck loading (see AdminGate).
        setError(
          e instanceof ApiError
            ? `Could not load your profile (${e.status}): ${e.message}`
            : String(e),
        );
      } finally {
        setLoading(false);
      }
    });
  }, []);

  async function signIn() {
    setError(null);
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function signOutUser() {
    await signOut(auth);
  }

  return (
    <AuthContext.Provider
      value={{ firebaseUser, me, loading, error, signIn, signOutUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

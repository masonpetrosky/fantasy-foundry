import { useCallback, useEffect, useRef, useState } from "react";
import { AUTH_SYNC_ENABLED, SUPABASE_PREFS_TABLE, loadSupabaseClient } from "../supabase_client";
import {
  CLOUD_SYNC_DEBOUNCE_MS,
  buildCloudPreferencesPayload,
  calculatorPresetsEqual,
  formatAuthError,
  mergeCalculatorPresetsPreferLocal,
  normalizeCloudPreferences,
} from "../app_state_storage";
import type { CalculatorPreset, PlayerWatchEntry } from "../app_state_storage";

/** Minimal shape of a Supabase auth user for our sync logic. */
interface AuthUser {
  id: string;
  email?: string;
  [key: string]: unknown;
}

/** Supabase-like client returned by loadSupabaseClient(). */
interface SupabaseClient {
  auth: {
    onAuthStateChange: (
      callback: (event: string, session: { user?: AuthUser | null } | null) => void,
    ) => { data: { subscription: { unsubscribe: () => void } } };
    getSession: () => Promise<{
      data: { session: { user?: AuthUser | null } | null } | null;
      error: { message?: string } | null;
    }>;
    signInWithPassword: (credentials: {
      email: string;
      password: string;
    }) => Promise<{ error: { message?: string } | null }>;
    signUp: (credentials: {
      email: string;
      password: string;
    }) => Promise<{
      data: { session: unknown } | null;
      error: { message?: string } | null;
    }>;
    signOut: () => Promise<{ error: { message?: string } | null }>;
  };
  from: (table: string) => {
    select: (columns: string) => {
      eq: (col: string, val: string) => {
        maybeSingle: () => Promise<{
          data: { preferences?: unknown } | null;
          error: { message?: string } | null;
        }>;
      };
    };
    upsert: (
      row: Record<string, unknown>,
      options?: { onConflict?: string },
    ) => Promise<{ error: { message?: string } | null }>;
  };
}

export interface UseAccountSyncInput {
  presets: Record<string, CalculatorPreset>;
  setPresets: React.Dispatch<React.SetStateAction<Record<string, CalculatorPreset>>>;
  watchlist: Record<string, PlayerWatchEntry>;
  setWatchlist: React.Dispatch<React.SetStateAction<Record<string, PlayerWatchEntry>>>;
}

export interface UseAccountSyncReturn {
  authReady: boolean;
  authUser: AuthUser | null;
  authStatus: string;
  cloudStatus: string;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

async function getSupabaseClient(): Promise<SupabaseClient | null> {
  return (await loadSupabaseClient()) as SupabaseClient | null;
}

export function useAccountSync({
  presets,
  setPresets,
  watchlist,
  setWatchlist,
}: UseAccountSyncInput): UseAccountSyncReturn {
  const [authReady, setAuthReady] = useState(!AUTH_SYNC_ENABLED);
  const [authUser, setAuthUser] = useState<AuthUser | null>(null);
  const [authStatus, setAuthStatus] = useState("");
  const [cloudStatus, setCloudStatus] = useState("");
  const [cloudReadyForSave, setCloudReadyForSave] = useState(false);
  const presetsRef = useRef(presets);
  const watchlistRef = useRef(watchlist);

  useEffect(() => {
    presetsRef.current = presets;
  }, [presets]);

  useEffect(() => {
    watchlistRef.current = watchlist;
  }, [watchlist]);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED) return undefined;
    let mounted = true;
    let unsubscribe: (() => void) | null = null;

    const setupAuth = async (): Promise<void> => {
      let client: SupabaseClient | null;
      try {
        client = await getSupabaseClient();
      } catch (error: unknown) {
        if (!mounted) return;
        setAuthStatus(`Account setup error: ${formatAuthError(error as { message?: string }, "Unable to initialize account sync.")}`);
        setAuthReady(true);
        return;
      }

      if (!mounted || !client) {
        if (mounted) setAuthReady(true);
        return;
      }

      const { data: authState } = client.auth.onAuthStateChange((_event, session) => {
        setAuthUser(session?.user || null);
        setCloudReadyForSave(false);
        if (!session?.user) {
          setCloudStatus("");
        }
      });
      unsubscribe = () => authState?.subscription?.unsubscribe();

      const { data, error } = await client.auth.getSession();
      if (!mounted) return;
      if (error) {
        setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to restore session.")}`);
      } else if (!data?.session) {
        setAuthStatus("Sign in to sync your presets and watchlist across devices.");
      }
      setAuthUser(data?.session?.user || null);
      setAuthReady(true);
    };

    setupAuth().catch((error: unknown) => {
      if (!mounted) return;
      setAuthStatus(`Account setup error: ${formatAuthError(error as { message?: string }, "Unable to initialize account sync.")}`);
      setAuthReady(true);
    });

    return () => {
      mounted = false;
      if (typeof unsubscribe === "function") unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authReady) return undefined;
    if (!authUser?.id) {
      setCloudReadyForSave(false);
      return undefined;
    }

    let cancelled = false;
    setCloudStatus("Syncing account settings...");
    setCloudReadyForSave(false);

    const loadCloudPreferences = async (): Promise<void> => {
      let client: SupabaseClient | null;
      try {
        client = await getSupabaseClient();
      } catch (error: unknown) {
        if (cancelled) return;
        setCloudStatus(`Cloud sync error: ${formatAuthError(error as { message?: string }, "Unable to initialize account settings.")}`);
        return;
      }
      if (!client || cancelled) return;

      const { data, error } = await client
        .from(SUPABASE_PREFS_TABLE)
        .select("preferences")
        .eq("user_id", authUser.id)
        .maybeSingle();

      if (cancelled) return;
      if (error) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unable to load account settings.")}`);
        return;
      }

      if (data?.preferences) {
        const normalized = normalizeCloudPreferences(data.preferences);
        const mergedCalculatorPresets = mergeCalculatorPresetsPreferLocal(
          presetsRef.current,
          normalized.calculatorPresets,
        );
        const shouldPersistMergedPresets = !calculatorPresetsEqual(
          mergedCalculatorPresets,
          normalized.calculatorPresets,
        );

        setPresets(mergedCalculatorPresets);
        setWatchlist(normalized.playerWatchlist);

        if (shouldPersistMergedPresets) {
          const mergedPayload = buildCloudPreferencesPayload({
            calculatorPresets: mergedCalculatorPresets,
            playerWatchlist: normalized.playerWatchlist,
          });
          const { error: mergeError } = await client
            .from(SUPABASE_PREFS_TABLE)
            .upsert(
              {
                user_id: authUser.id,
                preferences: mergedPayload,
              },
              { onConflict: "user_id" },
            );

          if (cancelled) return;
          if (mergeError) {
            setCloudStatus(`Cloud sync error: ${formatAuthError(mergeError, "Unable to merge account presets.")}`);
            return;
          }
          setCloudStatus("Merged local and cloud presets.");
          setCloudReadyForSave(true);
          return;
        }

        setCloudStatus("Loaded saved account settings.");
        setCloudReadyForSave(true);
        return;
      }

      const seedPayload = buildCloudPreferencesPayload({
        calculatorPresets: presetsRef.current,
        playerWatchlist: watchlistRef.current,
      });

      const { error: upsertError } = await client
        .from(SUPABASE_PREFS_TABLE)
        .upsert(
          {
            user_id: authUser.id,
            preferences: seedPayload,
          },
          { onConflict: "user_id" },
        );

      if (cancelled) return;
      if (upsertError) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(upsertError, "Unable to initialize account settings.")}`);
        return;
      }

      setCloudStatus("Cloud sync enabled.");
      setCloudReadyForSave(true);
    };

    loadCloudPreferences().catch((error: unknown) => {
      if (cancelled) return;
      setCloudStatus(`Cloud sync error: ${formatAuthError(error as { message?: string }, "Unexpected sync failure.")}`);
    });

    return () => {
      cancelled = true;
    };
  }, [authReady, authUser?.id, setPresets, setWatchlist]);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authUser?.id || !cloudReadyForSave) return undefined;

    const timer = window.setTimeout(async () => {
      let client: SupabaseClient | null;
      try {
        client = await getSupabaseClient();
      } catch (error: unknown) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error as { message?: string }, "Unable to initialize cloud sync.")}`);
        return;
      }
      if (!client) return;

      const payload = buildCloudPreferencesPayload({
        calculatorPresets: presets,
        playerWatchlist: watchlist,
      });
      const { error } = await client
        .from(SUPABASE_PREFS_TABLE)
        .upsert(
          {
            user_id: authUser.id,
            preferences: payload,
          },
          { onConflict: "user_id" },
        );
      if (error) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error, "Unable to save settings.")}`);
        return;
      }
      setCloudStatus("Saved account settings.");
    }, CLOUD_SYNC_DEBOUNCE_MS);

    return () => {
      window.clearTimeout(timer);
    };
  }, [authUser?.id, cloudReadyForSave, presets, watchlist]);

  const signIn = useCallback(async (email: string, password: string): Promise<void> => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign in failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await getSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signInWithPassword({
        email: normalizedEmail,
        password: normalizedPassword,
      });
      if (error) {
        setAuthStatus(`Sign in failed: ${formatAuthError(error, "Invalid login.")}`);
        return;
      }
      setAuthStatus("Signed in.");
    } catch (error: unknown) {
      setAuthStatus(`Sign in failed: ${formatAuthError(error as { message?: string }, "Unable to reach account service.")}`);
    }
  }, []);

  const signUp = useCallback(async (email: string, password: string): Promise<void> => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign up failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await getSupabaseClient();
      if (!client) return;
      const { data, error } = await client.auth.signUp({
        email: normalizedEmail,
        password: normalizedPassword,
      });
      if (error) {
        setAuthStatus(`Sign up failed: ${formatAuthError(error, "Unable to create account.")}`);
        return;
      }
      if (data?.session) {
        setAuthStatus("Account created. You are signed in.");
        return;
      }
      setAuthStatus("Account created. Check your email to confirm your login.");
    } catch (error: unknown) {
      setAuthStatus(`Sign up failed: ${formatAuthError(error as { message?: string }, "Unable to reach account service.")}`);
    }
  }, []);

  const signOut = useCallback(async (): Promise<void> => {
    if (!AUTH_SYNC_ENABLED) return;
    try {
      const client = await getSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signOut();
      if (error) {
        setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to sign out.")}`);
        return;
      }
      setAuthStatus("Signed out.");
      setCloudStatus("");
    } catch (error: unknown) {
      setAuthStatus(`Sign out failed: ${formatAuthError(error as { message?: string }, "Unable to reach account service.")}`);
    }
  }, []);

  return {
    authReady,
    authUser,
    authStatus,
    cloudStatus,
    signIn,
    signUp,
    signOut,
  };
}

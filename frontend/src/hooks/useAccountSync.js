import { useCallback, useEffect, useRef, useState } from "react";
import { AUTH_SYNC_ENABLED, SUPABASE_PREFS_TABLE, loadSupabaseClient } from "../supabase_client.js";
import {
  CLOUD_SYNC_DEBOUNCE_MS,
  buildCloudPreferencesPayload,
  calculatorPresetsEqual,
  formatAuthError,
  mergeCalculatorPresetsPreferLocal,
  normalizeCloudPreferences,
} from "../app_state_storage.js";

export function useAccountSync({ presets, setPresets, watchlist, setWatchlist }) {
  const [authReady, setAuthReady] = useState(!AUTH_SYNC_ENABLED);
  const [authUser, setAuthUser] = useState(null);
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
    let unsubscribe = null;

    const setupAuth = async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        if (!mounted) return;
        setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to initialize account sync.")}`);
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

    setupAuth().catch(error => {
      if (!mounted) return;
      setAuthStatus(`Account setup error: ${formatAuthError(error, "Unable to initialize account sync.")}`);
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

    const loadCloudPreferences = async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        if (cancelled) return;
        setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unable to initialize account settings.")}`);
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
          normalized.calculatorPresets
        );
        const shouldPersistMergedPresets = !calculatorPresetsEqual(
          mergedCalculatorPresets,
          normalized.calculatorPresets
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
              { onConflict: "user_id" }
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
          { onConflict: "user_id" }
        );

      if (cancelled) return;
      if (upsertError) {
        setCloudStatus(`Cloud sync error: ${formatAuthError(upsertError, "Unable to initialize account settings.")}`);
        return;
      }

      setCloudStatus("Cloud sync enabled.");
      setCloudReadyForSave(true);
    };

    loadCloudPreferences().catch(error => {
      if (cancelled) return;
      setCloudStatus(`Cloud sync error: ${formatAuthError(error, "Unexpected sync failure.")}`);
    });

    return () => {
      cancelled = true;
    };
  }, [authReady, authUser?.id, setPresets, setWatchlist]);

  useEffect(() => {
    if (!AUTH_SYNC_ENABLED || !authUser?.id || !cloudReadyForSave) return undefined;

    const timer = window.setTimeout(async () => {
      let client = null;
      try {
        client = await loadSupabaseClient();
      } catch (error) {
        setCloudStatus(`Cloud save error: ${formatAuthError(error, "Unable to initialize cloud sync.")}`);
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
          { onConflict: "user_id" }
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

  const signIn = useCallback(async (email, password) => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign in failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await loadSupabaseClient();
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
    } catch (error) {
      setAuthStatus(`Sign in failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  const signUp = useCallback(async (email, password) => {
    if (!AUTH_SYNC_ENABLED) return;
    const normalizedEmail = String(email || "").trim();
    const normalizedPassword = String(password || "");
    if (!normalizedEmail || !normalizedPassword) {
      setAuthStatus("Sign up failed: email and password are required.");
      return;
    }
    setAuthStatus("");
    try {
      const client = await loadSupabaseClient();
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
    } catch (error) {
      setAuthStatus(`Sign up failed: ${formatAuthError(error, "Unable to reach account service.")}`);
    }
  }, []);

  const signOut = useCallback(async () => {
    if (!AUTH_SYNC_ENABLED) return;
    try {
      const client = await loadSupabaseClient();
      if (!client) return;
      const { error } = await client.auth.signOut();
      if (error) {
        setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to sign out.")}`);
        return;
      }
      setAuthStatus("Signed out.");
      setCloudStatus("");
    } catch (error) {
      setAuthStatus(`Sign out failed: ${formatAuthError(error, "Unable to reach account service.")}`);
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

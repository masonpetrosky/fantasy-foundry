const DEFAULT_PREFS_TABLE = "user_preferences";

const SUPABASE_URL = String(import.meta.env.VITE_SUPABASE_URL || "").trim();
const SUPABASE_ANON_KEY = String(import.meta.env.VITE_SUPABASE_ANON_KEY || "").trim();

export const SUPABASE_PREFS_TABLE =
  String(import.meta.env.VITE_SUPABASE_PREFS_TABLE || DEFAULT_PREFS_TABLE).trim() ||
  DEFAULT_PREFS_TABLE;
export const AUTH_SYNC_ENABLED = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

export function createSupabaseClientLoader({
  enabled,
  supabaseUrl,
  supabaseAnonKey,
  importSupabaseModule = () => import("@supabase/supabase-js"),
}) {
  let client = null;
  let pending = null;

  return async function loadSupabaseClient() {
    if (!enabled) return null;
    if (client) return client;
    if (!pending) {
      pending = importSupabaseModule()
        .then(module => {
          if (!module || typeof module.createClient !== "function") {
            throw new Error("Supabase module is missing createClient.");
          }
          client = module.createClient(supabaseUrl, supabaseAnonKey, {
            auth: {
              persistSession: true,
              autoRefreshToken: true,
            },
          });
          return client;
        })
        .catch(error => {
          pending = null;
          throw error;
        });
    }
    return pending;
  };
}

export const loadSupabaseClient = createSupabaseClientLoader({
  enabled: AUTH_SYNC_ENABLED,
  supabaseUrl: SUPABASE_URL,
  supabaseAnonKey: SUPABASE_ANON_KEY,
});

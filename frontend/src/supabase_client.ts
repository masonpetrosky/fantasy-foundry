interface SupabaseModule {
  createClient: (url: string, key: string, options: Record<string, unknown>) => unknown;
}

const DEFAULT_PREFS_TABLE = "user_preferences";

const SUPABASE_URL = String(import.meta.env.VITE_SUPABASE_URL || "").trim();
const SUPABASE_ANON_KEY = String(import.meta.env.VITE_SUPABASE_ANON_KEY || "").trim();

export const SUPABASE_PREFS_TABLE =
  String(import.meta.env.VITE_SUPABASE_PREFS_TABLE || DEFAULT_PREFS_TABLE).trim() ||
  DEFAULT_PREFS_TABLE;
export const AUTH_SYNC_ENABLED = Boolean(SUPABASE_URL && SUPABASE_ANON_KEY);

export interface SupabaseClientLoaderOptions {
  enabled: boolean;
  supabaseUrl: string;
  supabaseAnonKey: string;
  importSupabaseModule?: () => Promise<SupabaseModule>;
}

export function createSupabaseClientLoader({
  enabled,
  supabaseUrl,
  supabaseAnonKey,
  importSupabaseModule = () => import("@supabase/supabase-js") as unknown as Promise<SupabaseModule>,
}: SupabaseClientLoaderOptions): () => Promise<unknown> {
  let client: unknown = null;
  let pending: Promise<unknown> | null = null;

  return async function loadSupabaseClient(): Promise<unknown> {
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

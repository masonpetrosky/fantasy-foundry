interface SentryModule {
  init: (options: { dsn: string; tracesSampleRate: number; environment: string }) => void;
  captureException: (error: unknown, context?: { extra: Record<string, unknown> }) => void;
}

let sentryModule: SentryModule | null = null;

export function initSentry(): void {
  const dsn = String(import.meta.env.VITE_SENTRY_DSN_FRONTEND || "").trim();
  if (!dsn) return;

  import("@sentry/react")
    .then(mod => {
      mod.init({
        dsn,
        tracesSampleRate: 0.05,
        environment: import.meta.env.MODE || "production",
      });
      sentryModule = mod;
    })
    .catch(() => {
      // Sentry failed to load — no-op.
    });
}

export function captureException(error: unknown, context?: Record<string, unknown>): void {
  if (!sentryModule) return;
  sentryModule.captureException(error, context ? { extra: context } : undefined);
}

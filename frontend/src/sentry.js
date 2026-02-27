let sentryModule = null;

export function initSentry() {
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

export function captureException(error, context) {
  if (!sentryModule) return;
  sentryModule.captureException(error, context ? { extra: context } : undefined);
}

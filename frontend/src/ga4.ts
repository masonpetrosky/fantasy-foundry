/**
 * Dynamically inject the Google Analytics 4 gtag.js snippet.
 *
 * Uses import.meta.env so Vite substitutes the measurement ID at build time,
 * avoiding the unreliable %VITE_*% HTML placeholder syntax.
 */

export function initGA4(): void {
  const id = String(import.meta.env.VITE_GA4_MEASUREMENT_ID || "").trim();
  if (!id) return;

  const script = document.createElement("script");
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${id}`;
  document.head.appendChild(script);

  window.dataLayer = window.dataLayer || [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  function gtag(...args: any[]): void { window.dataLayer!.push(args as any); }
  gtag("js", new Date());
  gtag("config", id);
}

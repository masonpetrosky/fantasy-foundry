import { useEffect, useRef, useState } from "react";
import { BUILD_QUERY_PARAM, BUILD_STORAGE_KEY, safeReadStorage, safeWriteStorage } from "../app_state_storage";

const INDEX_BUILD_ID = (() => {
  const metaEl = document.querySelector('meta[name="ff-build-id"]');
  const value = String(metaEl?.getAttribute("content") || "").trim();
  return value.startsWith("__APP_BUILD_") ? "" : value;
})();
const VERSION_POLL_INTERVAL_MS = 60000;

export function useVersionPolling(apiBase: string): { buildLabel: string; dataVersion: string } {
  const [buildLabel, setBuildLabel] = useState("");
  const [dataVersion, setDataVersion] = useState("");
  const versionEtagRef = useRef("");

  useEffect(() => {
    let cancelled = false;
    let timer: number | null = null;
    let activeController: AbortController | null = null;

    const scheduleNextPoll = (): void => {
      if (cancelled) return;
      timer = window.setTimeout(runVersionCheck, VERSION_POLL_INTERVAL_MS);
    };

    const runVersionCheck = async (): Promise<void> => {
      if (cancelled) return;
      if (activeController) activeController.abort();
      const controller = new AbortController();
      activeController = controller;
      const headers: Record<string, string> = { "Cache-Control": "no-cache" };
      if (versionEtagRef.current) {
        headers["If-None-Match"] = versionEtagRef.current;
      }

      try {
        const response = await fetch(`${apiBase}/api/version`, {
          signal: controller.signal,
          cache: "no-store",
          headers,
        });
        if (response.status === 304) return;
        if (!response.ok) throw new Error(`Server returned ${response.status} while loading /api/version`);

        const etag = String(response.headers.get("etag") || "").trim();
        if (etag) {
          versionEtagRef.current = etag;
        }

        const res = await response.json();
        if (cancelled) return;

        const buildId = String(res?.build_id || "").trim();
        const resolvedDataVersion = String(res?.data_version || buildId || "").trim();
        if (resolvedDataVersion) {
          setDataVersion(resolvedDataVersion);
        }
        if (!buildId) return;

        setBuildLabel(buildId.slice(0, 12));

        const previousBuildId = safeReadStorage(BUILD_STORAGE_KEY);
        const url = new URL(window.location.href);
        const urlBuildId = String(url.searchParams.get(BUILD_QUERY_PARAM) || "").trim();

        const pageIsStale = Boolean(INDEX_BUILD_ID && INDEX_BUILD_ID !== buildId);
        const seenBuildChange = Boolean(previousBuildId && previousBuildId !== buildId);
        if ((pageIsStale || seenBuildChange) && urlBuildId !== buildId) {
          url.searchParams.set(BUILD_QUERY_PARAM, buildId);
          window.location.replace(url.toString());
          return;
        }

        if (urlBuildId && urlBuildId !== buildId) {
          url.searchParams.set(BUILD_QUERY_PARAM, buildId);
          window.history.replaceState({}, "", url.toString());
        }

        safeWriteStorage(BUILD_STORAGE_KEY, buildId);
      } catch (err) {
        if ((err as Error)?.name === "AbortError" || cancelled) return;
        console.warn("Version check failed:", err);
      } finally {
        if (activeController === controller) {
          activeController = null;
        }
        scheduleNextPoll();
      }
    };

    runVersionCheck();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
      if (activeController) {
        activeController.abort();
        activeController = null;
      }
    };
  }, [apiBase]);

  return { buildLabel, dataVersion };
}

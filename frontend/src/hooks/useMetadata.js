import { useCallback, useEffect, useState } from "react";
import { trackEvent } from "../analytics.js";

export function useMetadata(apiBase) {
  const [meta, setMeta] = useState(null);
  const [metaError, setMetaError] = useState("");
  const [metaLoading, setMetaLoading] = useState(true);
  const [metaRequestNonce, setMetaRequestNonce] = useState(0);

  const retryMetaLoad = useCallback(() => {
    setMetaRequestNonce(value => value + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setMetaLoading(true);
    setMetaError("");
    fetch(`${apiBase}/api/meta`, { signal: controller.signal })
      .then(r => {
        if (!r.ok) {
          throw new Error(`Server returned ${r.status} while loading /api/meta.`);
        }
        return r.json();
      })
      .then(res => {
        setMeta(res);
        setMetaLoading(false);
      })
      .catch(err => {
        if (err?.name === "AbortError") return;
        const message = String(err?.message || "").trim();
        setMetaError(message || "Failed to load metadata.");
        setMetaLoading(false);
        trackEvent("meta_load_error", { message: message || "unknown", section: "projections" });
        console.error(err);
      });
    return () => {
      controller.abort();
    };
  }, [apiBase, metaRequestNonce]);

  return { meta, metaError, metaLoading, retryMetaLoad };
}

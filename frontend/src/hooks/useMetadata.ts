import { useCallback, useEffect, useState } from "react";
import { trackEvent } from "../analytics";
import { captureException } from "../sentry";
import { extractApiErrorMessage } from "../utils/apiErrors";

export function useMetadata(apiBase: string): {
  meta: Record<string, unknown> | null;
  metaError: string;
  metaLoading: boolean;
  retryMetaLoad: () => void;
} {
  const [meta, setMeta] = useState<Record<string, unknown> | null>(null);
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
        if ((err as Error)?.name === "AbortError") return;
        const message = extractApiErrorMessage(err);
        setMetaError(message);
        setMetaLoading(false);
        trackEvent("meta_load_error", { message: message || "unknown", section: "projections" });
        captureException(err, { source: "meta_load" });
      });
    return () => {
      controller.abort();
    };
  }, [apiBase, metaRequestNonce]);

  return { meta, metaError, metaLoading, retryMetaLoad };
}

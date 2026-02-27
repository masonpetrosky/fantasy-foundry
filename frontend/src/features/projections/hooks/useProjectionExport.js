import { useCallback } from "react";
import { trackEvent } from "../../../analytics";
import { parseDownloadFilename } from "../../../download_filename.js";
import { triggerBlobDownload } from "../../../download_helpers.js";
import { formatApiError, readResponsePayload } from "../../../request_helpers.js";

export async function executeProjectionExportRequest({
  endpointTab,
  href,
  format,
  watchlistOnly,
  yearView,
  hasCalculatorOverlay,
}) {
  trackEvent("export_click", {
    format,
    tab: endpointTab,
    watchlistOnly,
    yearView,
    hasCalculatorOverlay,
  });

  const response = await fetch(href, {
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });
  if (!response.ok) {
    const parsed = await readResponsePayload(response);
    throw new Error(formatApiError(response.status, parsed.payload, parsed.rawText));
  }

  const blob = await response.blob();
  const fallback = `projections-${endpointTab}.${format}`;
  const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
  triggerBlobDownload(filename, blob);
}

export function useProjectionExport() {
  const executeProjectionExport = useCallback(async request => {
    await executeProjectionExportRequest(request);
  }, []);

  return {
    executeProjectionExport,
  };
}

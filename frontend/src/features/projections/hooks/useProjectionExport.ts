import { useCallback } from "react";
import { trackEvent } from "../../../analytics";
import { parseDownloadFilename } from "../../../download_filename";
import { triggerBlobDownload } from "../../../download_helpers";
import { formatApiError, readResponsePayload } from "../../../request_helpers";

export interface ProjectionExportRequest {
  endpointTab: string;
  href: string;
  format: string;
  watchlistOnly: boolean;
  yearView: string;
  hasCalculatorOverlay: boolean;
}

export async function executeProjectionExportRequest({
  endpointTab,
  href,
  format,
  watchlistOnly,
  yearView,
  hasCalculatorOverlay,
}: ProjectionExportRequest): Promise<void> {
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
    throw new Error(formatApiError(response.status, parsed.payload as Parameters<typeof formatApiError>[1], parsed.rawText));
  }

  const blob = await response.blob();
  const fallback = `projections-${endpointTab}.${format}`;
  const filename = parseDownloadFilename(response.headers.get("content-disposition"), fallback);
  triggerBlobDownload(filename, blob);
}

export interface UseProjectionExportResult {
  executeProjectionExport: (request: ProjectionExportRequest) => Promise<void>;
}

export function useProjectionExport(): UseProjectionExportResult {
  const executeProjectionExport = useCallback(async (request: ProjectionExportRequest) => {
    await executeProjectionExportRequest(request);
  }, []);

  return {
    executeProjectionExport,
  };
}

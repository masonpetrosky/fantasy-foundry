import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import { extractApiErrorMessage } from "../utils/apiErrors";
import type { ProjectionRow } from "../app_state_storage";

type ProjectionTab = "all" | "bat" | "pitch";

interface ProjectionQueryResult {
  rows: ProjectionRow[];
  total: number;
}

interface UseProjectionsQueryInput {
  apiBase: string;
  endpointTab: ProjectionTab;
  params: URLSearchParams;
  enabled: boolean;
  resolvedDataVersion: string;
}

async function fetchProjections(
  apiBase: string,
  endpointTab: ProjectionTab,
  params: URLSearchParams,
  signal: AbortSignal,
): Promise<ProjectionQueryResult> {
  const response = await fetch(`${apiBase}/api/projections/${endpointTab}?${params}`, {
    signal,
    cache: "no-store",
    headers: { "Cache-Control": "no-cache" },
  });
  if (!response.ok) {
    throw new Error(`Server returned ${response.status} while loading projections`);
  }
  const payload: unknown = await response.json();
  const payloadObj = payload as Record<string, unknown>;
  const pageRows = Array.isArray(payloadObj.data) ? (payloadObj.data as ProjectionRow[]) : [];
  const parsedTotal = Number(payloadObj.total);
  const resolvedTotal = Number.isFinite(parsedTotal) && parsedTotal >= 0 ? parsedTotal : pageRows.length;
  const typeTag = endpointTab === "bat" ? "H" : endpointTab === "pitch" ? "P" : "";
  const rows = typeTag ? pageRows.map(row => ({ ...row, Type: typeTag })) : pageRows;
  return { rows, total: resolvedTotal };
}

export function useProjectionsQuery({
  apiBase,
  endpointTab,
  params,
  enabled,
  resolvedDataVersion,
}: UseProjectionsQueryInput) {
  const queryClient = useQueryClient();
  const queryKey = ["projections", resolvedDataVersion, endpointTab, params.toString()] as const;

  const result = useQuery({
    queryKey,
    queryFn: ({ signal }) => fetchProjections(apiBase, endpointTab, params, signal),
    enabled,
    placeholderData: keepPreviousData,
  });

  function prefetchNextPage(nextParams: URLSearchParams): void {
    const nextKey = ["projections", resolvedDataVersion, endpointTab, nextParams.toString()] as const;
    void queryClient.prefetchQuery({
      queryKey: nextKey,
      queryFn: ({ signal }) => fetchProjections(apiBase, endpointTab, nextParams, signal),
    });
  }

  function invalidateAll(): void {
    void queryClient.invalidateQueries({ queryKey: ["projections"] });
  }

  return {
    data: result.data ?? null,
    isLoading: result.isLoading,
    isFetching: result.isFetching,
    isError: result.isError,
    error: result.error ? extractApiErrorMessage(result.error) : "",
    prefetchNextPage,
    invalidateAll,
  };
}

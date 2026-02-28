import { useEffect, useRef, useState } from "react";
import type { ProjectionRow } from "../app_state_storage";

export function useDefaultDynastyPlayers(apiBase: string): ProjectionRow[] {
  const [rows, setRows] = useState<ProjectionRow[]>([]);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    const controller = new AbortController();
    const params = new URLSearchParams({
      include_dynasty: "true",
      career_totals: "true",
      sort_col: "DynastyValue",
      sort_dir: "desc",
      limit: "2000",
    });

    fetch(`${apiBase}/api/projections/all?${params}`, { signal: controller.signal })
      .then(res => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((json: { data?: ProjectionRow[] }) => {
        if (Array.isArray(json.data)) {
          setRows(json.data);
        }
      })
      .catch(() => {
        // Silent failure — returns [] on error
      });

    return () => controller.abort();
  }, [apiBase]);

  return rows;
}

import { useEffect, useState } from "react";

export interface DeltaMap {
  [playerEntityKey: string]: { composite_delta: number };
}

export interface ProjectionDeltasResponse {
  risers: DeltaMover[];
  fallers: DeltaMover[];
  delta_map: DeltaMap;
  has_previous: boolean;
}

export interface DeltaMover {
  key: string;
  player: string;
  team: string;
  pos: string;
  type: string;
  deltas: Record<string, number>;
  composite_delta: number;
}

export function useProjectionDeltas(apiBase: string): {
  deltaMap: DeltaMap;
  hasPrevious: boolean;
  risers: DeltaMover[];
  fallers: DeltaMover[];
  loading: boolean;
} {
  const [data, setData] = useState<ProjectionDeltasResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(`${apiBase}/api/projections/deltas`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<ProjectionDeltasResponse>;
      })
      .then((json) => {
        if (!cancelled) setData(json);
      })
      .catch(() => {
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiBase]);

  return {
    deltaMap: data?.delta_map ?? {},
    hasPrevious: data?.has_previous ?? false,
    risers: data?.risers ?? [],
    fallers: data?.fallers ?? [],
    loading,
  };
}

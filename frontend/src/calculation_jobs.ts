import { formatApiError, readResponsePayload, sleepWithAbort } from "./request_helpers";

export async function cancelCalculationJob(apiBase: unknown, jobId: unknown): Promise<void> {
  const normalizedApiBase = String(apiBase || "").trim();
  const normalizedJobId = String(jobId || "").trim();
  if (!normalizedJobId) return;
  try {
    await fetch(`${normalizedApiBase}/api/calculate/jobs/${encodeURIComponent(normalizedJobId)}`, {
      method: "DELETE",
    });
  } catch {
    // Best-effort cancel path; ignore network errors.
  }
}

function elapsedSecondsFromIso(isoText: unknown): number | null {
  const parsedMs = Date.parse(String(isoText || ""));
  if (!Number.isFinite(parsedMs)) return null;
  return Math.max(0, Math.round((Date.now() - parsedMs) / 1000));
}

interface CalculationJobPayload {
  [key: string]: unknown;
}

export interface RunCalculationJobInput {
  apiBase: unknown;
  payload: CalculationJobPayload | null;
  controller: AbortController;
  requestSeq: number;
  requestSeqRef: { current: number };
  activeJobIdRef: { current: string };
  timeoutSeconds: number;
  onStatus: (message: string) => void;
  onCompleted: (result: Record<string, unknown>, meta: { jobId: string }) => void;
  onCancelled: () => void;
  onError: (message: string) => void;
}

export async function runCalculationJob({
  apiBase,
  payload,
  controller,
  requestSeq,
  requestSeqRef,
  activeJobIdRef,
  timeoutSeconds,
  onStatus,
  onCompleted,
  onCancelled,
  onError,
}: RunCalculationJobInput): Promise<void> {
  const normalizedApiBase = String(apiBase || "").trim();
  const body = payload && typeof payload === "object" ? payload : null;
  if (!body) {
    onError("Invalid calculation request.");
    return;
  }

  const runningStatusLabel = "Running simulations...";
  let jobId = "";

  try {
    const createResp = await fetch(`${normalizedApiBase}/api/calculate/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    const createParsed = await readResponsePayload(createResp);
    if (!createResp.ok) {
      throw new Error(formatApiError(createResp.status, createParsed.payload as Record<string, unknown>, createParsed.rawText));
    }
    const initialJobPayload = createParsed.payload && typeof createParsed.payload === "object"
      ? createParsed.payload as Record<string, unknown>
      : {} as Record<string, unknown>;

    jobId = String((createParsed.payload as Record<string, unknown>)?.job_id || "").trim();
    if (!jobId) {
      throw new Error("Server did not return a calculation job id.");
    }
    activeJobIdRef.current = jobId;

    const maxWaitMs = Number.isFinite(timeoutSeconds) && timeoutSeconds > 0
      ? timeoutSeconds * 1000
      : 10 * 60 * 1000;
    const deadline = Date.now() + maxWaitMs;

    while (true) {
      if (requestSeq !== requestSeqRef.current || controller.signal.aborted) {
        if (jobId) {
          void cancelCalculationJob(normalizedApiBase, jobId);
          if (activeJobIdRef.current === jobId) {
            activeJobIdRef.current = "";
          }
        }
        return;
      }
      if (Date.now() > deadline) {
        throw new Error("Calculation timed out before completion.");
      }

      const statusResp = await fetch(`${normalizedApiBase}/api/calculate/jobs/${encodeURIComponent(jobId)}`, {
        signal: controller.signal,
      });
      const statusParsed = await readResponsePayload(statusResp);
      if (!statusResp.ok) {
        throw new Error(formatApiError(statusResp.status, statusParsed.payload as Record<string, unknown>, statusParsed.rawText));
      }

      const statusPayload = statusParsed.payload as Record<string, unknown>;
      const jobStatus = String(statusPayload?.status || "").toLowerCase();
      if (jobStatus === "queued") {
        const queuePosition = Number(statusPayload?.queue_position);
        const queuedJobs = Number(statusPayload?.queued_jobs);
        const queueLabel = Number.isFinite(queuePosition) && queuePosition > 0
          ? `queue ${queuePosition}${Number.isFinite(queuedJobs) && queuedJobs > 0 ? `/${queuedJobs}` : ""}`
          : "queued";
        const queueElapsed = elapsedSecondsFromIso(
          statusPayload?.created_at || initialJobPayload.created_at
        );
        onStatus(
          `${runningStatusLabel} (${queueLabel}${queueElapsed != null ? ` \u00b7 ${queueElapsed}s` : ""})`
        );
        await sleepWithAbort(1200, controller.signal);
        continue;
      }
      if (jobStatus === "running") {
        const runningElapsed = elapsedSecondsFromIso(
          statusPayload?.started_at ||
          statusPayload?.created_at ||
          initialJobPayload.created_at
        );
        onStatus(
          `${runningStatusLabel}${runningElapsed != null ? ` (${runningElapsed}s elapsed)` : ""}`
        );
        await sleepWithAbort(1200, controller.signal);
        continue;
      }
      if (jobStatus === "completed") {
        const result = statusPayload?.result as Record<string, unknown> | undefined;
        if (!result || !Array.isArray(result.data)) {
          throw new Error("Calculation completed without a usable result payload.");
        }
        if (requestSeq !== requestSeqRef.current || controller.signal.aborted) return;
        if (activeJobIdRef.current === jobId) {
          activeJobIdRef.current = "";
        }
        onCompleted(result, { jobId });
        return;
      }
      if (jobStatus === "cancelled" || jobStatus === "canceled") {
        if (activeJobIdRef.current === jobId) {
          activeJobIdRef.current = "";
        }
        onCancelled();
        return;
      }
      if (jobStatus === "failed") {
        const error = statusPayload?.error as Record<string, unknown> | undefined;
        const detail = typeof error?.detail === "string" ? error.detail : "";
        const errorStatus = Number(error?.status_code);
        if (activeJobIdRef.current === jobId) {
          activeJobIdRef.current = "";
        }
        if (detail && Number.isFinite(errorStatus)) {
          throw new Error(formatApiError(errorStatus, { detail }));
        }
        if (detail) {
          throw new Error(detail);
        }
        throw new Error("Calculation job failed.");
      }

      throw new Error("Unexpected calculation job status.");
    }
  } catch (err) {
    if (jobId) {
      void cancelCalculationJob(normalizedApiBase, jobId);
      if (activeJobIdRef.current === jobId) {
        activeJobIdRef.current = "";
      }
    }
    if (requestSeq !== requestSeqRef.current) return;
    if ((err as Error)?.name === "AbortError") return;
    onError((err as Error)?.message || "Calculation failed.");
  }
}

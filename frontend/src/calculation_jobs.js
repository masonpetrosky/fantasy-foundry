import { formatApiError, readResponsePayload, sleepWithAbort } from "./request_helpers.js";

export async function cancelCalculationJob(apiBase, jobId) {
  const normalizedApiBase = String(apiBase || "").trim();
  const normalizedJobId = String(jobId || "").trim();
  if (!normalizedApiBase || !normalizedJobId) return;
  try {
    await fetch(`${normalizedApiBase}/api/calculate/jobs/${encodeURIComponent(normalizedJobId)}`, {
      method: "DELETE",
    });
  } catch {
    // Best-effort cancel path; ignore network errors.
  }
}

function elapsedSecondsFromIso(isoText) {
  const parsedMs = Date.parse(String(isoText || ""));
  if (!Number.isFinite(parsedMs)) return null;
  return Math.max(0, Math.round((Date.now() - parsedMs) / 1000));
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
}) {
  const normalizedApiBase = String(apiBase || "").trim();
  const body = payload && typeof payload === "object" ? payload : null;
  if (!normalizedApiBase || !body) {
    onError("Invalid calculation request.");
    return;
  }

  const runningStatusLabel = body.scoring_mode === "points"
    ? "Running points valuation..."
    : "Running Monte Carlo simulations...";
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
      throw new Error(formatApiError(createResp.status, createParsed.payload, createParsed.rawText));
    }
    const initialJobPayload = createParsed.payload && typeof createParsed.payload === "object"
      ? createParsed.payload
      : {};

    jobId = String(createParsed.payload?.job_id || "").trim();
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
        throw new Error(formatApiError(statusResp.status, statusParsed.payload, statusParsed.rawText));
      }

      const jobStatus = String(statusParsed.payload?.status || "").toLowerCase();
      if (jobStatus === "queued") {
        const queuePosition = Number(statusParsed.payload?.queue_position);
        const queuedJobs = Number(statusParsed.payload?.queued_jobs);
        const queueLabel = Number.isFinite(queuePosition) && queuePosition > 0
          ? `queue ${queuePosition}${Number.isFinite(queuedJobs) && queuedJobs > 0 ? `/${queuedJobs}` : ""}`
          : "queued";
        const queueElapsed = elapsedSecondsFromIso(
          statusParsed.payload?.created_at || initialJobPayload.created_at
        );
        onStatus(
          `${runningStatusLabel} (${queueLabel}${queueElapsed != null ? ` · ${queueElapsed}s` : ""})`
        );
        await sleepWithAbort(1200, controller.signal);
        continue;
      }
      if (jobStatus === "running") {
        const runningElapsed = elapsedSecondsFromIso(
          statusParsed.payload?.started_at ||
          statusParsed.payload?.created_at ||
          initialJobPayload.created_at
        );
        onStatus(
          `${runningStatusLabel}${runningElapsed != null ? ` (${runningElapsed}s elapsed)` : ""}`
        );
        await sleepWithAbort(1200, controller.signal);
        continue;
      }
      if (jobStatus === "completed") {
        const result = statusParsed.payload?.result;
        if (!result || !Array.isArray(result.data)) {
          throw new Error("Calculation completed without a usable result payload.");
        }
        if (requestSeq !== requestSeqRef.current || controller.signal.aborted) return;
        if (activeJobIdRef.current === jobId) {
          activeJobIdRef.current = "";
        }
        onCompleted(result);
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
        const error = statusParsed.payload?.error;
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
    if (err?.name === "AbortError") return;
    onError(err?.message || "Calculation failed.");
  }
}

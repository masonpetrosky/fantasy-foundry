#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

IMAGE_TAG="${IMAGE_TAG:-fantasy-foundry-smoke:local}"
HOST_PORT="${HOST_PORT:-${1:-18000}}"
HEALTH_TIMEOUT_SECONDS="${HEALTH_TIMEOUT_SECONDS:-60}"
HEALTH_POLL_INTERVAL_SECONDS="${HEALTH_POLL_INTERVAL_SECONDS:-1}"
CONTAINER_NAME="${CONTAINER_NAME:-fantasy-foundry-smoke-${HOST_PORT}-$$}"
BASE_URL="http://127.0.0.1:${HOST_PORT}"

TMP_DIR="$(mktemp -d)"
BUILD_LOG="${TMP_DIR}/docker-build.log"
RUN_LOG="${TMP_DIR}/docker-run.log"

cleanup() {
  docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  rm -rf "${TMP_DIR}"
}

fail() {
  echo "[smoke-docker] FAIL $1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

check_endpoint() {
  local path="$1"
  local status
  status="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "${BASE_URL}${path}" 2>/dev/null || true)"
  if [[ "${status}" != "200" ]]; then
    fail "${path} returned HTTP ${status:-000}"
  fi
  echo "[smoke-docker] PASS ${path}"
}

wait_for_health() {
  local deadline status
  deadline=$((SECONDS + HEALTH_TIMEOUT_SECONDS))

  while (( SECONDS < deadline )); do
    status="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "${BASE_URL}/api/health" 2>/dev/null || true)"
    if [[ "${status}" == "200" ]]; then
      echo "[smoke-docker] PASS /api/health"
      return 0
    fi
    sleep "${HEALTH_POLL_INTERVAL_SECONDS}"
  done

  echo "[smoke-docker] Container logs:" >&2
  docker logs --tail 50 "${CONTAINER_NAME}" >&2 || true
  fail "/api/health did not return 200 within ${HEALTH_TIMEOUT_SECONDS}s"
}

require_cmd docker
require_cmd curl

echo "[smoke-docker] Building image ${IMAGE_TAG}"
if ! docker build -t "${IMAGE_TAG}" "${REPO_ROOT}" >"${BUILD_LOG}" 2>&1; then
  cat "${BUILD_LOG}" >&2
  fail "docker build -t ${IMAGE_TAG} ${REPO_ROOT}"
fi

echo "[smoke-docker] Starting container ${CONTAINER_NAME} on port ${HOST_PORT}"
if ! docker run \
  --name "${CONTAINER_NAME}" \
  -d \
  -p "${HOST_PORT}:8000" \
  "${IMAGE_TAG}" >"${RUN_LOG}" 2>&1; then
  cat "${RUN_LOG}" >&2
  fail "docker run --name ${CONTAINER_NAME} -d -p ${HOST_PORT}:8000 ${IMAGE_TAG}"
fi

trap cleanup EXIT INT TERM

echo "[smoke-docker] Waiting for /api/health"
wait_for_health
check_endpoint "/"
check_endpoint "/api/meta"

echo "[smoke-docker] PASS all checks"

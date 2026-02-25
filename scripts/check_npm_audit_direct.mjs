#!/usr/bin/env node
import { spawnSync } from "node:child_process";

function runNpmAudit() {
  return spawnSync("npm", ["audit", "--omit=dev", "--json"], {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function parseAuditOutput(raw) {
  const text = String(raw || "").trim();
  if (!text) return {};
  return JSON.parse(text);
}

function collectBlockingVulns(payload) {
  const vulnerabilities = payload && typeof payload === "object" ? payload.vulnerabilities : null;
  if (!vulnerabilities || typeof vulnerabilities !== "object") return [];

  const blocking = [];
  for (const [name, meta] of Object.entries(vulnerabilities)) {
    if (!meta || typeof meta !== "object") continue;
    const severity = String(meta.severity || "").toLowerCase();
    const isDirect = Boolean(meta.isDirect);
    if (!isDirect) continue;
    if (severity !== "high" && severity !== "critical") continue;
    blocking.push({ name, severity, range: String(meta.range || "unknown") });
  }
  return blocking;
}

function main() {
  const result = runNpmAudit();
  if (![0, 1].includes(result.status ?? 0)) {
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    process.exit(result.status ?? 2);
  }

  let payload = {};
  try {
    payload = parseAuditOutput(result.stdout);
  } catch (error) {
    console.error(`Failed to parse npm audit JSON output: ${error}`);
    process.exit(2);
  }

  const blocking = collectBlockingVulns(payload);
  if (blocking.length > 0) {
    console.error("Direct frontend dependencies with high/critical vulnerabilities detected:");
    for (const vuln of blocking.sort((a, b) => a.name.localeCompare(b.name))) {
      console.error(` - ${vuln.name} (${vuln.severity}, range: ${vuln.range})`);
    }
    process.exit(1);
  }

  console.log("No high/critical vulnerabilities found in direct frontend dependencies.");
}

main();

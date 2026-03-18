import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const plugins = [react()];
const manualChunkGroups = [
  { name: "vendor-react", packages: ["react", "react-dom", "react-router-dom"] },
  { name: "vendor-sentry", packages: ["@sentry/react"] },
  { name: "vendor-supabase", packages: ["@supabase/supabase-js"] },
  { name: "vendor-tanstack", packages: ["@tanstack/react-query", "@tanstack/react-virtual"] },
];

function resolveManualChunk(id) {
  if (!id.includes("node_modules")) {
    return undefined;
  }

  for (const group of manualChunkGroups) {
    for (const packageName of group.packages) {
      if (id.includes(`/node_modules/${packageName}/`)) {
        return group.name;
      }
    }
  }

  return undefined;
}

if (process.env.ANALYZE === "true") {
  const { visualizer } = await import("rollup-plugin-visualizer");
  plugins.push(
    visualizer({ open: true, filename: "stats.html", gzipSize: true }),
  );
}

export default defineConfig({
  plugins,
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{js,jsx,ts,tsx}"],
    exclude: ["dist/**", "node_modules/**"],
    setupFiles: ["src/test/setup.ts"],
    coverage: {
      provider: "v8",
      reporter: ["text", "lcov"],
      include: ["src/**/*.{js,jsx,ts,tsx}"],
      exclude: ["src/**/*.test.{js,jsx,ts,tsx}"],
      thresholds: {
        lines: 60,
        branches: 60,
        functions: 60,
        statements: 60,
      },
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    sourcemap: "hidden",
    target: "es2022",
    rollupOptions: {
      output: {
        manualChunks: resolveManualChunk,
      },
    },
  },
});

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const plugins = [react()];

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
        lines: 55,
        branches: 55,
        functions: 55,
        statements: 55,
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
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-sentry": ["@sentry/react"],
          "vendor-supabase": ["@supabase/supabase-js"],
          "vendor-tanstack": ["@tanstack/react-query"],
        },
      },
    },
  },
});

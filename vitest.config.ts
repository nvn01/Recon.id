import { fileURLToPath } from "node:url";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "~": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  test: {
    environment: "node",
    env: {
      DATABASE_URL: "postgresql://recon:test@127.0.0.1:5432/recon_test",
    },
    coverage: {
      provider: "v8",
      include: ["src/server/listings/**/*.ts", "src/server/api/routers/listings.ts"],
      exclude: ["**/*.test.ts"],
      thresholds: {
        branches: 80,
        functions: 80,
        lines: 80,
        statements: 80,
      },
    },
  },
});

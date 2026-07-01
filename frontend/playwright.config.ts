import { defineConfig } from "@playwright/test";

// The E2E workflow starts the backend, worker, and frontend; these specs drive
// the real app at localhost:3003.
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  retries: 1,
  reporter: "line",
  use: {
    baseURL: "http://localhost:3003",
    headless: true,
  },
});

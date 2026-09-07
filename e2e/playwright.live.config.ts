import { defineConfig, devices } from "@playwright/test";
import base from "./playwright.config";

const live =
  process.env.BASE_URL || "https://roomcraft-e1312--rhandar-level-56hqwy9h.web.app";

export default defineConfig({
  ...base,
  webServer: undefined,
  use: {
    ...base.use,
    baseURL: live,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});

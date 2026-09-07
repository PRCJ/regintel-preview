import { expect, test } from "@playwright/test";

test.describe("Home / crawl shell", () => {
  test("shows brand, product nav, crawl form, and Eva", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "RegIntel" })).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Product views" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Home" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Documents" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Horizon" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pipeline" })).toBeVisible();
    await expect(page.locator("#crawlForm")).toBeVisible();
    await expect(page.getByRole("button", { name: "Start crawl" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Open Eva chat" })).toBeVisible();
  });

  test("loads extracted site cards", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("#siteList .site-card").first()).toBeVisible({ timeout: 30_000 });
  });

  test("opening a site shows PDF list and back returns home", async ({ page }) => {
    await page.goto("/");
    const card = page.locator("#siteList .site-card").first();
    await expect(card).toBeVisible({ timeout: 30_000 });
    await card.click();
    await expect(page.locator("#viewDetail")).toBeVisible();
    await expect(page.locator("#detailBack")).toBeVisible();
    await page.locator("#detailBack").click();
    await expect(page.locator("#viewHome")).toBeVisible();
    await expect(page.locator("#crawlForm")).toBeVisible();
  });
});

import { expect, test } from "@playwright/test";

test.describe("Horizon and Pipeline", () => {
  test("Horizon shows change cards or an empty state", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Horizon" }).click();
    await expect(page.locator("#viewHorizon")).toBeVisible();
    await expect(page.locator("#crawlForm")).toBeHidden();
    const cards = page.locator("#horizonList .pdf-card");
    const empty = page.locator("#horizonEmpty");
    await expect.poll(async () => (await cards.count()) + ((await empty.isVisible()) ? 1 : 0)).toBeGreaterThan(0);
    if ((await cards.count()) > 0) {
      await expect(cards.first()).toBeVisible();
    } else {
      await expect(empty).toBeVisible();
    }
  });

  test("Pipeline shows six metric cards", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Pipeline" }).click();
    await expect(page.locator("#viewPipeline")).toBeVisible();
    await expect(page.locator("#pipelineStats .metric")).toHaveCount(6);
    await expect(page.locator("#pipelineStats")).toContainText("Scored");
    await expect(page.locator("#pipelineStats")).toContainText("High+");
  });

  test("nav hash updates for product views", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Documents" }).click();
    await expect(page).toHaveURL(/#documents/);
    await page.getByRole("button", { name: "Pipeline" }).click();
    await expect(page).toHaveURL(/#pipeline/);
  });
});

test.describe("Eva widget", () => {
  test("opens chat panel", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Open Eva chat" }).click();
    await expect(page.locator("#evaPanel")).toBeVisible();
    await expect(page.locator("#evaInput")).toBeVisible();
    await page.locator("#evaClose").click();
    await expect(page.locator("#evaPanel")).toBeHidden();
  });
});

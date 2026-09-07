import { expect, test } from "@playwright/test";

test.describe("Documents scoring view", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Documents" }).click();
    await expect(page.locator("#viewDocuments")).toBeVisible();
  });

  test("defaults to high + critical and lists scored cards", async ({ page }) => {
    await expect(page.locator("#docBand")).toHaveValue("high");
    await expect(page.locator("#docCount")).toContainText("of");
    await expect(page.locator("#docList .pdf-card").first()).toBeVisible({ timeout: 30_000 });
    await expect(page.locator(".score-badge").first()).toBeVisible();
  });

  test("switching band to all shows more rows than high", async ({ page }) => {
    await page.locator("#docList .pdf-card").first().waitFor({ timeout: 30_000 });
    const highText = await page.locator("#docCount").innerText();
    const highN = parseInt(highText, 10);
    await page.locator("#docBand").selectOption("all");
    await expect.poll(async () => {
      const t = await page.locator("#docCount").innerText();
      return parseInt(t, 10);
    }).toBeGreaterThan(highN);
  });

  test("not_relevant filter only shows not-relevant badges", async ({ page }) => {
    await page.locator("#docBand").selectOption("not_relevant");
    const first = page.locator("#docList .pdf-card").first();
    await expect(first).toBeVisible({ timeout: 30_000 });
    await expect(first.locator(".score-badge")).toContainText(/not_relevant/i);
  });

  test("search narrows the list", async ({ page }) => {
    await page.locator("#docList .pdf-card").first().waitFor({ timeout: 30_000 });
    await page.locator("#docSearch").fill("zzzzzz-no-such-document");
    await expect(page.locator("#docEmpty")).toBeVisible();
    await page.locator("#docSearch").fill("");
    await expect(page.locator("#docList .pdf-card").first()).toBeVisible();
  });

  test("card opens drawer with reason and close works", async ({ page }) => {
    await page.locator("#docList .pdf-card").first().click();
    await expect(page.locator("#docDrawer")).toBeVisible();
    await expect(page.locator("#docDrawerTitle")).not.toHaveText(/^$/);
    await page.locator("#docDrawerClose").click();
    await expect(page.locator("#docDrawer")).toBeHidden();
  });

  test("hides crawl form while on Documents", async ({ page }) => {
    await expect(page.locator("#crawlForm")).toBeHidden();
  });
});

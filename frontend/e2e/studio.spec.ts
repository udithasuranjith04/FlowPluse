import { test, expect } from "@playwright/test";

test("studio renders a camera-first experience and preserves consent gating", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Understand spaces/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Connect your camera" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Preview camera" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Start monitoring" })).toBeDisabled();
  await page.getByRole("button", { name: "Observations" }).click();
  await expect(page.getByRole("heading", { name: "Signals worth reviewing." })).toBeVisible();
  await page.getByRole("button", { name: "Live overview" }).click();
  await page.setViewportSize({ width: 375, height: 812 });
  await expect(page.getByRole("heading", { name: /Understand spaces/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

import { test, expect } from "@playwright/test";

test("offline studio remains honest, navigable and responsive", async ({ page }) => {
  await page.route("**/api/**", (route) => route.abort("connectionrefused"));
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Understand spaces/ })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("backend");
  await expect(page.getByRole("button", { name: "Preview camera" })).toBeDisabled();
  await page.getByRole("button", { name: "About FlowPulse" }).click();
  await expect(page.getByRole("heading", { name: "Insight without identity." })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

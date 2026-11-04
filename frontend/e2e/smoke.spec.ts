import { expect, test } from "@playwright/test";

// Real browser smoke test for GitHub Actions. Does not need camera hardware,
// model weights, or permission to activate a video source.
test("FlowPulse opens, reaches the local API, and navigates café pages", async ({
  page,
  request,
}) => {
  const health = await request.get("http://127.0.0.1:8000/api/health");
  expect(health.ok()).toBe(true);

  await page.goto("/");
  await expect(page).toHaveTitle(/FlowPulse AI/);
  await expect(
    page.getByRole("navigation", { name: "Main navigation" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Camera setup", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Simple start. Smart insights." }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Shift summary", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "What did your camera see this shift?",
    }),
  ).toBeVisible();
});

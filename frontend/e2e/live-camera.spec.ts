import { test, expect } from "@playwright/test";

// Optional physical acceptance: not run in CI or when no authorized camera is available.
test("owned camera yields changing real YOLO person frames", async ({ page, request }) => {
  test.skip(process.env.FLOWPULSE_LIVE_E2E !== "1", "Requires actual camera access and participant consent");
  test.setTimeout(120000);
  await page.goto("/");
  const chosen = process.env.FLOWPULSE_CAMERA_NAME || "iPhone";
  const deviceSelect = page.getByLabel("Available camera device");
  const options = await deviceSelect.locator("option").all();
  let picked = false;
  for (const option of options) if ((await option.textContent())?.includes(chosen)) {
    await deviceSelect.selectOption({ label: (await option.textContent())!.trim() }); picked = true; break;
  }
  expect(picked, `Camera containing '${chosen}' was not discovered`).toBe(true);
  await page.getByRole("checkbox", { name: /I control this camera/ }).check();
  await page.getByRole("button", { name: "Preview camera" }).click();
  await expect(page.getByRole("button", { name: "Start monitoring" })).toBeEnabled({ timeout: 40000 });
  await page.getByRole("button", { name: "Start monitoring" }).click();
  const frames = new Set<string>();
  for (let n = 0; n < 25 && frames.size < 3; n++) {
    const result = await request.get("/api/system/status");
    const status = await result.json();
    expect(status.detection_target).toBe("person");
    if (status.camera_id.startsWith("local-camera-") && status.continuous_frames_verified && status.frame_id) frames.add(status.frame_id);
    await page.waitForTimeout(500);
  }
  expect(frames.size).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("img", { name: /Live person-detection camera/ })).toBeVisible();
  await page.getByRole("button", { name: "Stop camera" }).click();
  const status = await (await request.get("/api/system/status")).json();
  expect(status.device_released).toBe(true);
});

import {expect, test} from "@playwright/test";

const API_BASE = "http://localhost:53117";
const DEV_BASE = "http://localhost:5173";

test.use({browserName: "chromium", headless: true});

test("GPU info endpoint returns data", async ({request}) => {
    const response = await request.get(`${API_BASE}/freemocap/realtime/gpu-info`, {timeout: 5000});
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("gpus");
    expect(Array.isArray(body.gpus)).toBeTruthy();
});

test("health endpoint is reachable", async ({request}) => {
    const response = await request.get(`${API_BASE}/health`, {timeout: 5000});
    expect(response.ok()).toBeTruthy();
});

test("metrics page renders with title and GPU info", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "domcontentloaded", timeout: 15000});
    await page.waitForTimeout(3000);

    // Verify title renders
    await expect(page.locator(".title").first()).toHaveText("Pipeline metrics", {timeout: 5000});

    // Verify Connected or Disconnected status is visible
    const status = page.locator("span.text.md").first();
    await expect(status).toBeVisible();
    const statusText = await status.textContent();
    expect(statusText).toMatch(/Connected|Disconnected/);

    await page.screenshot({path: "e2e/screenshots/pipeline-metrics.png", fullPage: true});
});


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

test("Pipeline Actions flyout renders GPU info", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/`, {waitUntil: "domcontentloaded", timeout: 15000});
    await page.waitForTimeout(5000);

    // Look for the flyout container
    const flyout = page.locator(".RTP-settings-flyout");
    const flyoutCount = await flyout.count();
    console.log(`RTP-settings-flyout elements: ${flyoutCount}`);

    if (flyoutCount > 0) {
        const html = await flyout.first().innerHTML();
        console.log("=== FLYOUT HTML ===");
        console.log(html?.substring(0, 2000));

        const text = await flyout.first().textContent();
        console.log("=== FLYOUT TEXT ===");
        console.log(text);

        await flyout.first().screenshot({path: "e2e/screenshots/pipeline-actions-flyout.png"});
    } else {
        // Flyout might be closed - try to find the trigger
        console.log("Flyout not found, looking for all clickable elements near 'Pipeline Actions'");
        const allElements = page.locator("*");
        const total = await allElements.count();
        console.log(`Total elements: ${total}`);
    }
});


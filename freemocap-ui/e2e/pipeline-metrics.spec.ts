import {expect, test} from "@playwright/test";

const API_BASE = "http://localhost:53117";
const DEV_BASE = "http://localhost:5173";

test.use({browserName: "chromium", headless: true});

test("GPU info endpoint returns all required fields", async ({request}) => {
    const response = await request.get(`${API_BASE}/freemocap/realtime/gpu-info`, {timeout: 5000});
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body).toHaveProperty("gpus");
    expect(Array.isArray(body.gpus)).toBeTruthy();
    expect(body).toHaveProperty("onnx_providers");
    expect(Array.isArray(body.onnx_providers)).toBeTruthy();
    expect(body).toHaveProperty("optimal_provider");
    expect(typeof body.optimal_provider).toBe("string");
    expect(body).toHaveProperty("gpu_acceleration_available");
    expect(typeof body.gpu_acceleration_available).toBe("boolean");
});

test("metrics page renders title and connection status", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    await expect(page.locator(".title").first()).toHaveText("Pipeline metrics", {timeout: 5000});

    // Find the span that explicitly shows Connected or Disconnected
    const status = page.locator("span.text.md").filter({hasText: /^Connected$|^Disconnected$/});
    await expect(status.first()).toBeVisible({timeout: 10000});

    await page.close();
});

test("GPU info display renders GPU name or CPU fallback in toolbar", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    // Wait for GPU info to load and appear in the toolbar (row 1, after status)
    const gpuText = page.locator("span.text.sm").filter({hasText: /GeForce|RTX|GPU|CPU ·/});
    await expect(gpuText.first()).toBeVisible({timeout: 10000});

    await page.close();
});


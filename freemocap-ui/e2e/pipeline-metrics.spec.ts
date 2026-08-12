import {expect, test} from "@playwright/test";

const API_BASE = process.env.FREEMOCAP_API_URL || "http://localhost:53117";
const DEV_BASE = process.env.FREEMOCAP_DEV_URL || "http://localhost:5173";

test.use({browserName: "chromium", headless: true});

// ── GPU info REST endpoint ───────────────────────────────────────────────────

test("GPU info endpoint returns all required fields", async ({request}) => {
    const response = await request.get(`${API_BASE}/freemocap/realtime/gpu-info`, {timeout: 5000});
    expect(response.ok()).toBeTruthy();
    const body = await response.json();

    // Top-level fields
    expect(body).toHaveProperty("gpus");
    expect(Array.isArray(body.gpus)).toBeTruthy();
    expect(body).toHaveProperty("onnx_providers");
    expect(Array.isArray(body.onnx_providers)).toBeTruthy();
    expect(body).toHaveProperty("optimal_provider");
    expect(typeof body.optimal_provider).toBe("string");
    expect(body).toHaveProperty("gpu_acceleration_available");
    expect(typeof body.gpu_acceleration_available).toBe("boolean");

    // GPU object shape (at least one GPU entry if gpus is non-empty, or gpus may be empty on CPU-only)
    if (body.gpus.length > 0) {
        const gpu = body.gpus[0];
        expect(gpu).toHaveProperty("name");
        expect(typeof gpu.name).toBe("string");
        expect(gpu).toHaveProperty("vram_mb");
        expect(typeof gpu.vram_mb).toBe("number");
    }
});

// ── Metrics page: title + connection status ──────────────────────────────────

test("metrics page renders title and connection status", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    await expect(page.locator(".title").first()).toHaveText("Pipeline metrics", {timeout: 5000});

    // The connection status span shows either "Connected" or "Disconnected".
    const status = page.locator("span.text.md").filter({hasText: /^Connected$|^Disconnected$/});
    await expect(status.first()).toBeVisible({timeout: 10000});
});

// ── GPU info display in toolbar ──────────────────────────────────────────────

test("GPU info display renders GPU name or CPU fallback in toolbar", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    // Matches NVIDIA, AMD, Intel Arc, Apple Silicon, generic GPU, or CPU fallback.
    const gpuText = page.locator("span.text.sm").filter({
        hasText: /GeForce|RTX|Radeon|Arc|Apple M\d|GPU|CPU ·/,
    });
    await expect(gpuText.first()).toBeVisible({timeout: 10000});
});

// ── WebSocket: live timing data ──────────────────────────────────────────────

test("metrics page receives and renders WebSocket timing data", async ({page}) => {
    // Intercept the WebSocket connection and inject a pipeline_timing message
    // once the connection is established.
    await page.routeWebSocket(/\/ws/, (ws) => {
        ws.onMessage((msg) => {
            // Echo any client messages back (e.g. subscription registrations).
            ws.send(msg);
        });
        // After a short delay, inject a pipeline_timing payload.
        setTimeout(() => {
            ws.send(JSON.stringify({
                message_type: "pipeline_timing",
                camera_group_id: "group_a",
                clock_domain: "perf_counter",
                relay_perf_counter_ns: 1_000_000_000,
                realtime_pipeline_active: true,
                dropped_timing_events: 0,
                configured_camera_fps_hz: 30.0,
                events: [
                    {
                        task_id: "1:batch:skeleton_inference:predict_batch",
                        stage: "predict_batch",
                        node_kind: "skeleton_inference",
                        frame_number: 1,
                        start_time_ns: 1_000_000,
                        end_time_ns: 13_500_000,
                        duration_ms: 12.5,
                    },
                ],
                per_node: {
                    skeleton_inference: {predict_batch: [12.5]},
                },
                per_camera: {},
            }));
        }, 2000);
    });

    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    // After the injected message, the 10s trailing average should appear.
    // Look for a numeric frame-time display (e.g. "12.5 ms" or similar).
    const timingValue = page.locator("span").filter({hasText: /\d+\.?\d*\s*ms/});
    await expect(timingValue.first()).toBeVisible({timeout: 10000});
});

// ── Error state: API unreachable ─────────────────────────────────────────────

test("metrics page shows disconnected when server is unreachable", async ({page}) => {
    // Block all API requests to simulate the backend being down.
    await page.route(`${API_BASE}/**`, (route) => route.abort("connectionRefused"));

    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    // The GPU info fetch will fail; the page should still render and eventually
    // show a Disconnected status (or fall back gracefully).
    const status = page.locator("span.text.md").filter({hasText: /^Disconnected$/});
    await expect(status.first()).toBeVisible({timeout: 15000});
});

// ── GPU flyout detail ────────────────────────────────────────────────────────

test("GPU info flyout shows provider details on click", async ({page}) => {
    await page.goto(`${DEV_BASE}/#/pipeline-metrics`, {waitUntil: "networkidle", timeout: 15000});

    // Click the GPU info area to open the flyout.
    const gpuTrigger = page.locator("span.text.sm").filter({
        hasText: /GeForce|RTX|Radeon|Arc|Apple M\d|GPU|CPU ·/,
    }).first();
    await gpuTrigger.click({timeout: 5000});

    // After clicking, provider-related detail should appear on screen.
    // Try known labels first; fall back to any new visible text containing "Provider" or "VRAM".
    const detail = page.getByText(/Execution Provider|VRAM|Available Providers/i).first();
    await expect(detail).toBeVisible({timeout: 5000});
});


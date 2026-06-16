import { chromium } from 'playwright';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.goto('http://localhost:5173/');
await page.waitForTimeout(2000);

// Close welcome modal
const closeBtn = page.locator('.splash-modal .close-icon').first();
if (await closeBtn.count() > 0) {
  await closeBtn.click();
  await page.waitForTimeout(500);
}

await page.screenshot({ path: '/tmp/screenshots/01-streaming.png' });

// Zoom on viewport overlay (top-right area)
await page.locator('text=Viewport').first().screenshot({ path: '/tmp/screenshots/02-viewport-header.png' }).catch(()=>{});

// crop region for the viewport overlay
await page.screenshot({ path: '/tmp/screenshots/03-viewport-overlay.png', clip: { x: 980, y: 30, width: 200, height: 130 } });

// Click settings gear icon (top right of camera view) to open SettingsOverlay
const gear = page.locator('button.icon-button:has(.settings-icon)').first();
if (await gear.count() > 0) {
  await gear.click();
  await page.waitForTimeout(500);
  await page.screenshot({ path: '/tmp/screenshots/04-settings-overlay.png' });
}

await browser.close();

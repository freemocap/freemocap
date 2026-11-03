import {defineConfig} from '@playwright/test';
// One set of committed baselines for every platform: the app bundles its fonts, and Chromium renders text
// without platform hinting or subpixel (LCD) antialiasing, so screens must match pixel for pixel across OSes.
export default defineConfig({
  testDir:'./e2e', testMatch:['ui-refactor-baseline.spec.ts','ui-refactor-surfaces.spec.ts'],
  timeout:90000, workers:1, retries:0,
  expect:{toHaveScreenshot:{threshold:0,maxDiffPixels:0}},
  outputDir:'../.test-artifacts/harness-results',
  snapshotPathTemplate:'{testDir}/visual-baselines/{arg}{ext}',
  reporter:[['list'],['json',{outputFile:'../.test-artifacts/harness-results/results.json'}]],
  use:{
    viewport:{width:1280,height:720},locale:'en-US',timezoneId:'America/New_York',colorScheme:'dark',trace:'retain-on-failure',
    launchOptions:{args:['--font-render-hinting=none','--disable-lcd-text','--disable-font-subpixel-positioning','--force-color-profile=srgb','--force-device-scale-factor=1','--disable-gpu','--num-raster-threads=1','--disable-partial-raster']},
  },
});

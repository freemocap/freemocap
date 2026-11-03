import {defineConfig} from '@playwright/test';
export default defineConfig({
  testDir:'./e2e', testMatch:['ui-refactor-baseline.spec.ts','ui-refactor-surfaces.spec.ts'],
  timeout:90000, workers:1, retries:0,
  expect:{toHaveScreenshot:{threshold:0,maxDiffPixels:0}},
  outputDir:'../.test-artifacts/harness-results',
  snapshotPathTemplate:'{testDir}/../../.test-artifacts/baselines/{platform}/{arg}{ext}',
  reporter:[['list'],['json',{outputFile:'../.test-artifacts/harness-results/results.json'}]],
  use:{viewport:{width:1280,height:720},locale:'en-US',timezoneId:'America/New_York',colorScheme:'dark',trace:'retain-on-failure'},
});

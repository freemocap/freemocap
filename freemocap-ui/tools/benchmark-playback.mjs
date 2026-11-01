// Run from freemocap-ui: node tools/benchmark-playback.mjs <reference.parquet> <ignored-report.json>
// Uses installed Edge, the Core .venv, and production browser decoder/renderers. No installs.
import {build} from 'esbuild';
import {chromium} from '@playwright/test';
import {createServer} from 'node:http';
import {execFileSync} from 'node:child_process';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {resolve, dirname} from 'node:path';
import {createHash} from 'node:crypto';

const [referencePath, reportPath, displayOverridePath] = process.argv.slice(2).map(value => resolve(value));
if (!referencePath || !reportPath) throw new Error('Expected reference.parquet and ignored-report.json');
const python = resolve('../.venv/Scripts/python.exe');
const metadata = JSON.parse(execFileSync(python, ['-B', '-c', `
import json, sys, time
from pathlib import Path
from freemocap.core.recording.playback_queries import playback_manifest
samples = []
for attempt in range(6):
    start = time.perf_counter()
    manifest = playback_manifest(Path(sys.argv[1]))
    if attempt: samples.append((time.perf_counter() - start) * 1000)
print(json.dumps({'manifest': manifest.model_dump(mode='json'), 'samples_ms': samples}))
`, referencePath], {cwd: resolve('..'), encoding: 'utf8', windowsHide: true, maxBuffer: 32 * 1024 * 1024,
    env: {...process.env, PYTHONDONTWRITEBYTECODE: '1'}}));
const parquet = await readFile(referencePath);
// Optional test-only projection exercises new display declarations on identical
// recorded numerical values, without rewriting the recording or its saved model.
if (displayOverridePath) {
    const display = JSON.parse(await readFile(displayOverridePath, 'utf8'));
    for (const run of metadata.manifest.runs) for (const model of run.models) {
        if (model.model_id === display.model_id) {
            model.presentation = display.presentation;
            model.landmark_connections = display.landmark_connections;
            model.tracker_connections = display.tracker_connections;
        }
    }
}
const bundle = await build({entryPoints: ['tools/playback-benchmark-scene.tsx'], bundle: true, write: false,
    format: 'esm', platform: 'browser', jsx: 'automatic', alias: {'@': resolve('src')}});
const transferWorker = await build({entryPoints: ['tools/playback-transfer-benchmark.worker.ts'], bundle: true, write: false,
    format: 'esm', platform: 'browser', alias: {'@': resolve('src')}});
const server = createServer((request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    if (request.url === '/manifest.json') {response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(metadata.manifest));}
    else if (request.url === '/recording.parquet') response.end(parquet);
    else if (request.url === '/entry.js') {response.setHeader('Content-Type', 'text/javascript'); response.end(bundle.outputFiles[0].text);}
    else if (request.url === '/transfer-worker.js') {response.setHeader('Content-Type', 'text/javascript'); response.end(transferWorker.outputFiles[0].text);}
    else {response.setHeader('Content-Type', 'text/html'); response.end('<div id="root" style="width:800px;height:600px"></div><script type="module" src="/entry.js"></script>');}
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
let browser;
try {
    browser = await chromium.launch({channel: process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless: true,
        args: ['--enable-precise-memory-info']});
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => {if (message.type() === 'error') errors.push(message.text());});
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => typeof window.runPlaybackBenchmark === 'function');
    const result = await page.evaluate(() => window.runPlaybackBenchmark());
    if (errors.length) throw new Error(errors.join('\n'));
    if (!result.maximum_renderer_stats.rawKeypoints || !result.maximum_renderer_stats.boneLines) {
        throw new Error('Reference renderer did not draw keypoints and bones: ' + JSON.stringify(result.final_renderer_stats));
    }
    const samples = metadata.samples_ms;
    const report = {reference_path: referencePath, source_sha256: createHash('sha256').update(parquet).digest('hex'),
        source_bytes: parquet.byteLength, browser: await browser.version(), display_override: displayOverridePath ?? null,
        manifest_build: {median_ms: [...samples].sort((a, b) => a - b)[Math.floor(samples.length / 2)], samples_ms: samples},
        ...result,
        method: 'One warmup plus five samples; local HTTP bytes cached in server memory. Actual production renderer callbacks with WebGL submission measured separately. Five alternating paired display passes use identical numerical values; a test-only baseline removes the selected presentation metadata and new line groups. Separate real-worker round trips exercise the production viewport receiver/store and pooled transfers. Twenty model/visibility cycles inspect resources. Renderer timings exclude worker hops; worker timings exclude rendering. Playback readiness is covered by parquet-playback.spec.ts.',
        limitations: 'Not network/storage throughput, GPU completion time, full application startup, peak memory, total process RSS, or long-recording scaling. JS heap samples depend on garbage collection; retained channel byte count is deterministic.'};
    await mkdir(dirname(reportPath), {recursive: true});
    await writeFile(reportPath, JSON.stringify(report, null, 2) + '\n');
    await page.screenshot({path: reportPath.replace(/\.json$/, '.png')});
    const {channel_fingerprints, geometry_evidence, ...summary} = report;
    console.log(JSON.stringify(summary, null, 2));
} finally {
    if (browser) await browser.close();
    await new Promise((resolve, reject) => {server.close(error => error ? reject(error) : resolve()); server.closeAllConnections();});
}

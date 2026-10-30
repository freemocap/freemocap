// Run from freemocap-ui: node tools/benchmark-playback.mjs <reference.parquet> <ignored-report.json>
// Uses installed Edge, the Core .venv, and production browser decoder/renderers. No installs.
import {build} from 'esbuild';
import {chromium} from '@playwright/test';
import {createServer} from 'node:http';
import {execFileSync} from 'node:child_process';
import {readFile, writeFile, mkdir} from 'node:fs/promises';
import {resolve, dirname} from 'node:path';
import {createHash} from 'node:crypto';

const [referencePath, reportPath] = process.argv.slice(2).map(value => resolve(value));
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
const bundle = await build({entryPoints: ['tools/playback-benchmark-scene.tsx'], bundle: true, write: false,
    format: 'esm', platform: 'browser', jsx: 'automatic', alias: {'@': resolve('src')}});
const server = createServer((request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    if (request.url === '/manifest.json') {response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify(metadata.manifest));}
    else if (request.url === '/recording.parquet') response.end(parquet);
    else if (request.url === '/entry.js') {response.setHeader('Content-Type', 'text/javascript'); response.end(bundle.outputFiles[0].text);}
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
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => typeof window.runPlaybackBenchmark === 'function');
    const result = await page.evaluate(() => window.runPlaybackBenchmark());
    if (errors.length) throw new Error(errors.join('\n'));
    if (!result.maximum_renderer_stats.rawKeypoints || !result.maximum_renderer_stats.boneLines) {
        throw new Error('Reference renderer did not draw keypoints and bones: ' + JSON.stringify(result.final_renderer_stats));
    }
    const samples = metadata.samples_ms;
    const report = {reference_path: referencePath, source_sha256: createHash('sha256').update(parquet).digest('hex'),
        source_bytes: parquet.byteLength, browser: await browser.version(),
        manifest_build: {median_ms: [...samples].sort((a, b) => a - b)[Math.floor(samples.length / 2)], samples_ms: samples},
        ...result,
        method: 'One warmup plus five samples; local HTTP bytes cached in server memory. Frame measurements run all source frames per sample. Actual production renderer callbacks, with WebGL submission measured separately. No worker hop in renderer timings; playback readiness measured by parquet-playback.spec.ts.',
        limitations: 'Not network/storage throughput, GPU completion time, full application startup, peak memory, total process RSS, or long-recording scaling. JS heap samples depend on garbage collection; retained channel byte count is deterministic.'};
    await mkdir(dirname(reportPath), {recursive: true});
    await writeFile(reportPath, JSON.stringify(report, null, 2) + '\n');
    const {channel_fingerprints, geometry_evidence, ...summary} = report;
    console.log(JSON.stringify(summary, null, 2));
} finally {
    if (browser) await browser.close();
    await new Promise((resolve, reject) => {server.close(error => error ? reject(error) : resolve()); server.closeAllConnections();});
}

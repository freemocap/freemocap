import {test, expect, _electron as electron} from '@playwright/test';
import {createServer} from 'vite';
import {build} from 'esbuild';
import {mkdtemp, readFile, mkdir, copyFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawn} from 'node:child_process';
import {decode} from 'cbor-x';
import {PlaybackCommand, PlaybackEvent} from '../src/services/recording/playback-protocol';

test('app controller streams native frames for play, seek and source switching', async () => {
    test.setTimeout(120_000);
    const bytes = await readFile('e2e/fixtures/numbered-bframes.mp4');
    const requests: string[] = [];
    const temporary = await mkdtemp(join(tmpdir(), 'app-playback-test-'));
    for (const recording of ['test', 'test-other']) for (const annotated of [false, true]) {
        const folder = join(temporary, recording, annotated ? 'annotated_videos' : 'synchronized_videos');
        await mkdir(folder, {recursive: true});
        for (let index = 0; index < 2; index++) await copyFile('e2e/fixtures/numbered-bframes.mp4',
            join(folder, `camera${index}${annotated ? '_annotated' : ''}.mp4`));
    }
    const portFile = join(temporary, 'port.txt');
    const backend = spawn(resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python'),
        ['-m', 'freemocap.tests.playback_test_server', portFile], {cwd: resolve('..'), windowsHide: true});
    let backendErrors = '';
    backend.stderr.on('data', chunk => {backendErrors += String(chunk);});
    backend.stdout.resume();
    await expect.poll(async () => {
        if (backend.exitCode !== null) throw new Error(backendErrors);
        return readFile(portFile, 'utf8').catch(() => '');
    }, {timeout: 20_000}).not.toBe('');
    const backendPort = await readFile(portFile, 'utf8');
    const media = [false, true].flatMap(annotated => Array.from({length: 2}, (_, index) => ({
        video_filename: `camera${index}${annotated ? '_annotated' : ''}.mp4`, nominal_fps: 30,
        timeline: {sensor_group: 'cameras', source: `camera${index}`, frame_numbers: Array.from({length: 48}, (_, n) => n),
            timestamps_s: Array.from({length: 48}, (_, n) => n / 30 + index * 0.002)},
    })));
    const server = await createServer({configFile: false, root: resolve('prototypes/app-playback'),
        resolve: {alias: {'@': resolve('src')}},
        server: {host: '127.0.0.1', port: 0, watch: null, hmr: false, fs: {allow: [process.cwd()]}, proxy: {
            '/websocket/playback': {target: `http://127.0.0.1:${backendPort}`, ws: true,
                rewrite: path => `${path}?recording_parent_directory=${encodeURIComponent(temporary)}`},
        }},
        plugins: [{name: 'test-recording-api', configureServer(server) {
            server.middlewares.use((request, response, next) => {
                const url = request.url ?? '';
                if (!url.startsWith('/test-media/') && !url.startsWith('/freemocap/')) return next();
                requests.push(url);
                if (url.includes('/bundle')) {
                    response.setHeader('Content-Type', 'application/json');
                    response.end(JSON.stringify({manifest: null, media, videos: {sources: Object.fromEntries(
                        [false, true].map(annotated => [annotated ? 'annotated' : 'synchronized', {valid: true,
                            videos: media.filter(item => item.video_filename.includes('_annotated') === annotated).map(item => ({
                                filename: item.video_filename, videoId: item.video_filename, sizeBytes: bytes.length,
                                streamUrl: `${server.resolvedUrls!.local[0]}test-media/${item.video_filename}`,
                            }))}]))}})); return;
                }
                response.statusCode = 404; response.end();
            });
        }}]});
    const entry = join(temporary, 'main.cjs');
    await build({entryPoints: ['tools/media-electron.ts'], bundle: true, platform: 'node', format: 'cjs', external: ['electron'], outfile: entry});
    await server.listen();
    try {
        const app = await electron.launch({args: [entry, server.resolvedUrls!.local[0]], timeout: 20_000, env: {...process.env, MEDIA_TEST: '1'}});
        try {
            const page = await app.firstWindow();
            let deliveredFrames = 0;
            const rangeLengths: number[] = [];
            page.on('websocket', socket => {
                socket.on('framereceived', event => {
                    if (typeof event.payload !== 'string' && decode(event.payload).kind === PlaybackEvent.Frame) deliveredFrames++;
                });
                socket.on('framesent', event => {
                    const request = JSON.parse(String(event.payload));
                    if (request.command === PlaybackCommand.Range) rangeLengths.push(request.payload.end_frame - request.payload.start_frame);
                });
            });
            await expect(page.locator('#ready')).toHaveText('true', {timeout: 30_000});
            const assertOrdinal = async (ordinal: number): Promise<void> => {
                await expect.poll(async () => page.locator('canvas:not(.playback-cache-timeline)').evaluateAll(canvases => canvases.map(canvas => {
                    const snapshot = document.createElement('canvas');
                    snapshot.width = (canvas as HTMLCanvasElement).width;
                    snapshot.height = (canvas as HTMLCanvasElement).height;
                    const context = snapshot.getContext('2d')!;
                    context.drawImage(canvas as HTMLCanvasElement, 0, 0);
                    return Array.from({length: 8}, (_, bit) => context.getImageData((bit + 0.5) * (canvas as HTMLCanvasElement).width / 8, (canvas as HTMLCanvasElement).height / 2, 1, 1).data[0] > 128 ? 1 << bit : 0)
                        .reduce((value, bit) => value + bit, 0);
                }))).toEqual([ordinal, ordinal]);
                await expect(page.locator('#error')).toBeEmpty();
            };
            await assertOrdinal(0);
            await expect(page.getByText(/Display:/)).toContainText('\u2014');
            const tile = page.locator('.test-video-panel').first();
            await tile.scrollIntoViewIfNeeded();
            const image = tile.locator('canvas');
            const originalBounds = await image.boundingBox();
            if (!originalBounds) throw new Error('Playback image is not visible');
            const wheelAtCursor = async (delta: number): Promise<void> => {
                const viewport = await tile.boundingBox();
                const before = await image.boundingBox();
                if (!viewport || !before) throw new Error('Missing zoom viewport');
                const x = viewport.x + viewport.width * 0.63;
                const y = viewport.y + viewport.height * 0.42;
                const imageX = (x - before.x) / before.width;
                const imageY = (y - before.y) / before.height;
                await page.mouse.move(x, y);
                await page.mouse.wheel(0, delta);
                await expect.poll(async () => (await image.boundingBox())!.width).not.toBe(before.width);
                const after = await image.boundingBox();
                if (!after) throw new Error('Zoomed image is not visible');
                expect(Math.abs(after.x + imageX * after.width - x)).toBeLessThan(1);
                expect(Math.abs(after.y + imageY * after.height - y)).toBeLessThan(1);
            };
            for (const delta of [-120, -120, -120, 80]) await wheelAtCursor(delta);
            const tileBounds = await tile.boundingBox();
            if (!tileBounds) throw new Error('Missing zoom viewport');
            await page.mouse.move(tileBounds.x + 100, tileBounds.y + 100);
            await page.mouse.down();
            await page.mouse.move(tileBounds.x + 120, tileBounds.y + 110, {steps: 4});
            await page.mouse.up();
            await wheelAtCursor(-120);
            await tile.dblclick();
            await expect.poll(async () => (await image.boundingBox())!.width).toBeCloseTo(originalBounds.width);
            await expect.poll(async () => (await image.boundingBox())!.x).toBeCloseTo(originalBounds.x);

            expect(await page.locator('canvas:not(.playback-cache-timeline)').evaluateAll(canvases => canvases.every(canvas => {
                try {(canvas as HTMLCanvasElement).getContext('2d'); return false;}
                catch (error) {return error instanceof DOMException && error.name === 'InvalidStateError';}
            }))).toBe(true);
            const dimensions = (): Promise<number[][]> => page.locator('canvas:not(.playback-cache-timeline)').evaluateAll(
                canvases => canvases.map(canvas => [(canvas as HTMLCanvasElement).width, (canvas as HTMLCanvasElement).height]));
            const fullDimensions = await dimensions();
            await page.locator('#forward').click(); await assertOrdinal(30);
            await page.locator('#back').click(); await assertOrdinal(2);
            const slider = page.locator('input[type=range]');
            const bounds = await slider.boundingBox();
            if (!bounds) throw new Error('Timeline is not visible');
            await page.mouse.click(bounds.x + bounds.width * 0.65, bounds.y + bounds.height / 2);
            const clickedFrame = Number(await slider.inputValue());
            expect(clickedFrame).toBeGreaterThan(20);
            await assertOrdinal(clickedFrame);
            await expect(slider).toHaveValue(String(clickedFrame));
            await page.mouse.move(bounds.x + bounds.width * 0.65, bounds.y + bounds.height / 2);
            await page.mouse.down();
            await page.mouse.move(bounds.x + bounds.width * 0.25, bounds.y + bounds.height / 2, {steps: 8});
            await page.mouse.up();
            const draggedFrame = Number(await slider.inputValue());
            expect(draggedFrame).toBeLessThan(clickedFrame);
            await assertOrdinal(draggedFrame);
            await expect(slider).toHaveValue(String(draggedFrame));
            const readsBeforePlayback = requests.filter(url => url.startsWith('/test-media/')).length;
            await page.locator('#play').click();
            await expect.poll(dimensions).toEqual(fullDimensions.map(size => size.map(value => Math.floor(value / 2))));
            await expect(page.getByText(/Display:/)).toHaveText(/Display: [0-9]+\.[0-9] fps/);
            await expect(page.locator('#playing')).toHaveText('false', {timeout: 20_000});
            await assertOrdinal(47);
            await expect.poll(dimensions).toEqual(fullDimensions);
            expect(requests.filter(url => url.startsWith('/test-media/')).length).toBe(readsBeforePlayback);
            await page.locator('#source').click(); await assertOrdinal(47);
            await expect(slider).toHaveValue('47');
            await page.locator('#forward').click(); await assertOrdinal(30);
            await page.locator('#back').click(); await assertOrdinal(2);
            await page.locator('#play').click();
            await expect(page.locator('#playing')).toHaveText('false', {timeout: 20_000});
            await assertOrdinal(47);
            const readsBeforeSwitch = requests.filter(url => url.startsWith('/test-media/')).length;
            const framesBeforeSwitch = deliveredFrames;
            await page.locator('#source').click();
            await expect(page.locator('#ready')).toHaveText('true');
            await assertOrdinal(47);
            await page.locator('#source').click();
            await expect(page.locator('#ready')).toHaveText('true');
            await assertOrdinal(47);
            expect(requests.filter(url => url.startsWith('/test-media/')).length).toBe(readsBeforeSwitch);
            expect(deliveredFrames).toBe(framesBeforeSwitch);
            expect(requests.some(url => url.includes('/frames/'))).toBe(false);
            expect(requests.filter(url => url.startsWith('/test-media/'))).toHaveLength(0);
            expect(requests.filter(url => url.startsWith('/freemocap/')).every(url => url === '/freemocap/playback/test/bundle')).toBe(true);
            await expect.poll(() => page.locator('.playback-cache-timeline--jpeg').evaluate(canvas => {
                const surface = canvas as HTMLCanvasElement;
                const pixels = surface.getContext('2d')!.getImageData(0, 0, surface.width, surface.height).data;
                return pixels.some((value, index) => index % 4 === 3 && value > 0);
            })).toBe(true);
            await expect.poll(() => page.locator('.playback-cache-timeline--bitmap').evaluate(canvas => {
                const surface = canvas as HTMLCanvasElement;
                return surface.getContext('2d')!.getImageData(0, 0, surface.width, surface.height).data
                    .some((value, index) => index % 4 === 3 && value > 0);
            })).toBe(true);
            const coverage = await page.locator('.playback-cache-timeline').evaluateAll(canvases => canvases.map(element => {
                const canvas = element as HTMLCanvasElement;
                const pixels = canvas.getContext('2d')!.getImageData(0, 0, canvas.width, 1).data;
                return {color: getComputedStyle(canvas).color,
                    pixels: pixels.filter((value, index) => index % 4 === 3 && value > 0).length};
            }));
            expect(coverage[0].pixels).toBeGreaterThan(coverage[1].pixels);
            expect(coverage[0].color).not.toBe(coverage[1].color);
            await page.reload();
            await expect(page.locator('#ready')).toHaveText('true');
            await assertOrdinal(0);
            await page.locator('#source').click();
            await assertOrdinal(0);
            await page.locator('#forward').click(); await assertOrdinal(30);
            await page.locator('#recording').click(); await assertOrdinal(0);
            await page.locator('#play').click();
            await expect(page.locator('#playing')).toHaveText('true');
            await page.locator('#source').click();
            await expect(page.locator('#playing')).toHaveText('false');
            await assertOrdinal(Number(await slider.inputValue()));
            expect(rangeLengths.some(length => length > 4)).toBe(true);
            await page.locator('#forward').click(); await assertOrdinal(30);
            await page.locator('#recording').click(); await assertOrdinal(0);
            const rendererChecks = await page.evaluate(async (modulePath) => {
                const {ScheduledRenderer} = await import(modulePath);
                const canvas = document.createElement('canvas');
                const failures: string[] = [];
                const renderer = new ScheduledRenderer(canvas, (error: Error) => failures.push(error.message));
                try {
                    const image = await renderer.prepare(new Uint8Array([255, 0, 0, 255]).buffer, 1, 1);
                    renderer.release(image);
                    let rejected = false;
                    try {await renderer.present(image);} catch {rejected = true;}
                    return {rejected, failures};
                } finally {renderer.close();}
            }, `/@fs/${resolve('src/services/server/server-helpers/scheduled-renderer.ts').replaceAll('\\', '/')}`);
            expect(rendererChecks.rejected).toBe(true);
            expect(rendererChecks.failures).toHaveLength(1);
            // A failed renderer must not stop independent playback canvases.
            await page.locator('#forward').click(); await assertOrdinal(30);
            await page.locator('#back').click(); await assertOrdinal(2);
            await page.evaluate(async (modulePath) => {
                const {ScheduledRenderer} = await import(modulePath) as typeof import('../src/services/server/server-helpers/scheduled-renderer');
                const prepare = ScheduledRenderer.prototype.prepare;
                const present = ScheduledRenderer.prototype.present;
                const counters = Object.assign(window, {renderedCount: 0});
                ScheduledRenderer.prototype.prepare = async function (...args: Parameters<typeof prepare>) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                    return prepare.apply(this, args);
                };
                ScheduledRenderer.prototype.present = function (...args: Parameters<typeof present>) {
                    counters.renderedCount++;
                    return present.apply(this, args);
                };
            }, `/@fs/${resolve('src/services/server/server-helpers/scheduled-renderer.ts').replaceAll('\\', '/')}`);
            await page.locator('#play').click();
            await expect(page.locator('#playing')).toHaveText('true');
            await expect(page.locator('#playing')).toHaveText('false', {timeout: 20_000});
            await assertOrdinal(47);
            const presentations = await page.evaluate(() => (window as unknown as {renderedCount: number}).renderedCount);
            console.log('Slow-rendering presentation count:', presentations, 'FPS:', await page.getByText(/Display:/).textContent());
            expect(presentations).toBeGreaterThan((48 - 2));
            await expect.poll(async () => {
                const label = await page.getByText(/Display:/).textContent();
                return Number(label?.match(/Display: ([0-9.]+)/)?.[1]);
            }).toBeGreaterThan(4);

        } finally {await app.close();}
    } finally {await server.close(); backend.kill();}
});

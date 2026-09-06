import {test, expect, _electron as electron} from '@playwright/test';
import {createServer} from 'vite';
import {build} from 'esbuild';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

test('app controller uses buffered video bytes for play, seek and source switching', async () => {
    test.setTimeout(120_000);
    const bytes = await readFile('e2e/fixtures/numbered-bframes.mp4');
    const requests: string[] = [];
    let rangeRequests = 0;
    const media = [false, true].flatMap(annotated => Array.from({length: 2}, (_, index) => ({
        video_filename: `camera${index}${annotated ? '_annotated' : ''}.mp4`, nominal_fps: 30,
        timeline: {sensor_group: 'cameras', source: `camera${index}`, frame_numbers: Array.from({length: 48}, (_, n) => n),
            timestamps_s: Array.from({length: 48}, (_, n) => n / 30 + index * 0.002)},
    })));
    const server = await createServer({configFile: false, root: resolve('prototypes/app-playback'),
        optimizeDeps: {include: ['mediabunny']},
        resolve: {alias: {'@': resolve('src')}},
        server: {host: '127.0.0.1', port: 0, fs: {allow: [process.cwd()]}},
        plugins: [{name: 'test-recording-api', configureServer(server) {
            server.middlewares.use((request, response, next) => {
                const url = request.url ?? '';
                if (!url.startsWith('/test-media/') && !url.startsWith('/freemocap/')) return next();
                requests.push(url);
                if (url.includes('/bundle')) {response.setHeader('Content-Type', 'application/json'); response.end(JSON.stringify({manifest: null, media, videos: {sources: {
                    all: {videos: media.map(item => ({filename: item.video_filename, videoId: item.video_filename,
                        sizeBytes: bytes.length, streamUrl: `${server.resolvedUrls!.local[0]}test-media/${item.video_filename}`}))}
                }}})); return;}
                if (url.startsWith('/test-media/')) {
                    if (request.headers.range) rangeRequests++;
                    const range = /bytes=(\d+)-(\d*)/.exec(request.headers.range ?? '');
                    const start = range ? Number(range[1]) : 0;
                    const end = range?.[2] ? Math.min(Number(range[2]), bytes.length - 1) : bytes.length - 1;
                    response.statusCode = range ? 206 : 200;
                    response.setHeader('Content-Type', 'video/mp4'); response.setHeader('Accept-Ranges', 'bytes');
                    if (range) response.setHeader('Content-Range', `bytes ${start}-${end}/${bytes.length}`);
                    response.setHeader('Content-Length', end - start + 1);
                    response.end(bytes.subarray(start, end + 1)); return;
                }
                response.statusCode = 404; response.end();
            });
        }}]});
    const temporary = await mkdtemp(join(tmpdir(), 'app-playback-test-'));
    const entry = join(temporary, 'main.cjs');
    await build({entryPoints: ['tools/media-electron.ts'], bundle: true, platform: 'node', format: 'cjs', external: ['electron'], outfile: entry});
    await server.listen();
    try {
        const app = await electron.launch({args: [entry, server.resolvedUrls!.local[0]], timeout: 20_000, env: {...process.env, MEDIA_TEST: '1'}});
        try {
            const page = await app.firstWindow();
            await expect(page.locator('#ready')).toHaveText('true', {timeout: 30_000});
            const assertOrdinal = async (ordinal: number): Promise<void> => {
                await expect.poll(async () => page.locator('canvas').evaluateAll(canvases => canvases.map(canvas => {
                    const context = (canvas as HTMLCanvasElement).getContext('2d')!;
                    return Array.from({length: 8}, (_, bit) => context.getImageData(bit * 80 + 40, 240, 1, 1).data[0] > 128 ? 1 << bit : 0)
                        .reduce((value, bit) => value + bit, 0);
                }))).toEqual([ordinal, ordinal]);
                await expect(page.locator('#error')).toBeEmpty();
            };
            await assertOrdinal(0);
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
            await expect(page.locator('#playing')).toHaveText('false', {timeout: 20_000});
            await assertOrdinal(47);
            expect(requests.filter(url => url.startsWith('/test-media/')).length).toBe(readsBeforePlayback);
            await page.locator('#source').click(); await assertOrdinal(47);
            await expect(slider).toHaveValue('47');
            await page.locator('#forward').click(); await assertOrdinal(30);
            await page.locator('#back').click(); await assertOrdinal(2);
            await page.locator('#play').click();
            await expect(page.locator('#playing')).toHaveText('false', {timeout: 20_000});
            await assertOrdinal(47);
            const readsBeforeSwitch = requests.filter(url => url.startsWith('/test-media/')).length;
            await page.locator('#source').click();
            await expect(page.locator('#ready')).toHaveText('true');
            await assertOrdinal(47);
            await page.locator('#source').click();
            await expect(page.locator('#ready')).toHaveText('true');
            await assertOrdinal(47);
            expect(requests.filter(url => url.startsWith('/test-media/')).length).toBe(readsBeforeSwitch);
            expect(requests.some(url => url.includes('_annotated.mp4'))).toBe(true);
            expect(requests.some(url => url.includes('/frames/'))).toBe(false);
            expect(rangeRequests).toBe(0);
            expect(requests.filter(url => url.startsWith('/test-media/'))).toHaveLength(4);
            expect(requests.filter(url => url.startsWith('/freemocap/'))).toEqual(['/freemocap/playback/test/bundle']);
        } finally {await app.close();}
    } finally {await server.close();}
});

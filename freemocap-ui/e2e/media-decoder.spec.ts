import {test, expect, _electron as electron} from '@playwright/test';
import {createServer} from 'vite';
import {build} from 'esbuild';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {validateVideoGroup} from '../src/services/recording/synchronized-video-group';
import {FrameLookahead} from '../src/services/recording/frame-lookahead';

for (const videoCount of [1, 2, 5]) {
test(`Electron locks ${videoCount} videos to the same ordinal`, async () => {
    test.setTimeout(120_000);
    const server = await createServer({configFile: false, root: resolve('prototypes/media-decoder'),
        server: {host: '127.0.0.1', port: 0, fs: {allow: [process.cwd()]}}});
    const temporary = await mkdtemp(join(tmpdir(), 'media-electron-test-'));
    const entry = join(temporary, 'main.cjs');
    await build({entryPoints: ['tools/media-electron.ts'], bundle: true, platform: 'node',
        format: 'cjs', external: ['electron'], outfile: entry});
    await server.listen();
    try {
        const app = await electron.launch({args: [entry, server.resolvedUrls!.local[0]], timeout: 20_000,
            env: {...process.env, MEDIA_TEST: '1'}});
        try {
            const page = await app.firstWindow({timeout: 20_000});
            page.setDefaultTimeout(15_000);
            if (!!process.env.MEDIA_TEST_VIDEO !== !!process.env.MEDIA_TEST_REFERENCE) {
                throw new Error('Custom video tests require both MEDIA_TEST_VIDEO and MEDIA_TEST_REFERENCE');
            }
            const buffer = await readFile(process.env.MEDIA_TEST_VIDEO ?? 'e2e/fixtures/numbered-bframes.mp4');
            await page.locator('#file').setInputFiles(Array.from({length: videoCount}, (_, index) => ({name: `input-${index}.mp4`, mimeType: 'video/mp4', buffer})));
            await expect(page.locator('#status')).toContainText('Ready:');
            const references: number[][] = JSON.parse(await readFile(process.env.MEDIA_TEST_REFERENCE ?? 'e2e/fixtures/numbered-bframes.json', 'utf8'));
            for (const ordinal of [0, 30, 29, 30, 0, 47]) {
                await page.locator('#ordinal').fill(String(ordinal));
                await page.locator('#read').click();
                await expect(page.locator('#status')).toContainText(`"ordinal":${ordinal},`);
                const result = JSON.parse(await page.locator('#status').innerText());
                if (ordinal === 29) expect(result.cacheHit).toBe(true);
                if (ordinal === 47) expect(result.restarts).toBe(1);
                expect(result.videos).toBe(videoCount);
                const panes = await page.locator('canvas').evaluateAll((elements) => elements.map(element => {
                    const canvas = element as HTMLCanvasElement;
                    const context = canvas.getContext('2d')!;
                    return Array.from({length: 8}, (_, bit) => context.getImageData(bit * 80 + 40, 240, 1, 1).data[0]);
                }));
                expect(panes).toHaveLength(videoCount);
                panes.forEach(pixels => pixels.forEach((level, bit) => expect(Math.abs(level - references[ordinal][bit])).toBeLessThan(8)));
            }
            await page.locator('#ordinal').fill('0');
            // Pause at readiness, before this short fixture can finish between driver round trips.
            await page.evaluate(() => {
                const button = document.querySelector<HTMLButtonElement>('#pause')!;
                const observer = new MutationObserver(() => {
                    if (!button.disabled) {observer.disconnect(); button.click();}
                });
                observer.observe(button, {attributes: true, attributeFilter: ['disabled']});
            });
            await page.locator('#play').click();
            await expect(page.locator('#status')).toHaveText('Paused');
            const pausedOrdinals = await page.locator('canvas').evaluateAll(elements => elements.map(element => (element as HTMLCanvasElement).dataset.ordinal));
            expect(new Set(pausedOrdinals).size).toBe(1);
            await page.locator('#play').click();
            await expect(page.locator('#status')).toHaveText('Playback complete', {timeout: 20_000});
            const finalOrdinals = await page.locator('canvas').evaluateAll(elements => elements.map(element => (element as HTMLCanvasElement).dataset.ordinal));
            expect(finalOrdinals).toEqual(Array(videoCount).fill('47'));
        } finally { await app.close(); }
    } finally { await server.close(); }
});
}

test('synchronized groups require nonempty input and equal frame counts', () => {
    const first = {name: 'first.mp4', frameCount: 48};
    expect(() => validateVideoGroup([first, {...first, name: 'short.mp4', frameCount: 47}])).toThrow('Frame count mismatch');
    expect(validateVideoGroup([first, {...first, name: 'second.mp4'}])).toBe(48);
    expect(() => validateVideoGroup([])).toThrow('Select at least one');
});

test('lookahead is bounded and replenishes only consumed slots', async () => {
    const loaded: number[] = [];
    const released: number[] = [];
    const buffer = new FrameLookahead({start: 0, end: 10, capacity: 3,
        load: async (ordinal: number) => {loaded.push(ordinal); return ordinal;},
        release: (ordinal: number) => {released.push(ordinal);}});
    await buffer.fill();
    expect(loaded).toEqual([0, 1, 2]);
    expect(buffer.take()).toBe(0);
    await buffer.fill();
    expect(loaded).toEqual([0, 1, 2, 3]);
    await buffer.close();
    expect(released).toEqual([1, 2, 3]);
});

test('closing lookahead releases a frame still being decoded', async () => {
    let finish: (value: number) => void = () => {throw new Error('Load not started');};
    const released: number[] = [];
    const buffer = new FrameLookahead({start: 0, end: 2, capacity: 2,
        load: () => new Promise<number>(resolve => {finish = resolve;}),
        release: (ordinal: number) => {released.push(ordinal);}});
    const filling = buffer.fill();
    const closing = buffer.close();
    finish(0);
    await Promise.all([filling, closing]);
    expect(buffer.size).toBe(0);
    expect(released).toEqual([0]);
});

import {test, expect, _electron as electron} from '@playwright/test';
import {createServer} from 'vite';
import {build} from 'esbuild';
import {mkdtemp, readFile, mkdir, copyFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawn} from 'node:child_process';

for (const compatibility of [false, true]) test(`app playback plays, seeks, switches and reloads (conversion=${compatibility})`, async () => {
    test.setTimeout(120_000);
    const temporary = await mkdtemp(join(tmpdir(), 'native-app-playback-'));
    for (const annotated of [false, true]) {
        const folder = join(temporary, 'test', annotated ? 'annotated_videos' : 'synchronized_videos');
        await mkdir(folder, {recursive: true});
        for (let index = 0; index < 2; index++) await copyFile('e2e/fixtures/numbered-bframes.mp4', join(folder, `camera${index}${annotated ? '_annotated' : ''}.mp4`));
    }
    const portFile = join(temporary, 'port.txt');
    const backend = spawn(resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python'),
        ['-m', 'freemocap.tests.playback_test_server', portFile], {cwd: resolve('..'), windowsHide: true});
    let errors = '';
    backend.stderr.on('data', chunk => {errors += String(chunk);}); backend.stdout.resume();
    try {
        await expect.poll(async () => {
            if (backend.exitCode !== null) throw new Error(errors);
            return readFile(portFile, 'utf8').catch(() => '');
        }, {timeout: 30_000}).not.toBe('');
        const port = Number(await readFile(portFile, 'utf8'));
        const media = [false, true].flatMap(annotated => Array.from({length: 2}, (_, index) => ({
            video_source: annotated ? 'annotated' : 'synchronized',
            video_filename: `camera${index}${annotated ? '_annotated' : ''}.mp4`, nominal_fps: 30,
            timeline: {sensor_group: 'cameras', source: `camera${index}`, frame_numbers: Array.from({length: 48}, (_, n) => n),
                timestamps_s: Array.from({length: 48}, (_, n) => n / 30)},
        })));
        const server = await createServer({configFile: false, root: resolve('prototypes/app-playback'),
            resolve: {alias: {'@': resolve('src')}}, server: {host: '127.0.0.1', port: 0, hmr: false, watch: null,
                fs: {allow: [process.cwd()]}, proxy: {'/test-media': {target: `http://127.0.0.1:${port}`, rewrite: path => {
                    const url = new URL(path, 'http://test');
                    const filename = url.pathname.slice('/test-media/'.length);
                    if (compatibility && !filename.endsWith('/browser')) return '/unsupported-test-source';
                    url.searchParams.set('source', filename.includes('_annotated') ? 'annotated' : 'synchronized');
                    url.searchParams.set('recording_parent_directory', temporary);
                    return `/playback/test/videos/${filename}?${url.searchParams}`;
                }}}}, plugins: [{name: 'recording-bundle', configureServer(server) {
                    server.middlewares.use((request, response, next) => {
                        if (!request.url?.includes('/bundle')) return next();
                        response.setHeader('Content-Type', 'application/json');
                        response.end(JSON.stringify({manifest: null, media, videos: {sources: Object.fromEntries(
                            [false, true].map(annotated => [annotated ? 'annotated' : 'synchronized', {valid: true,
                                videos: media.filter(item => item.video_filename.includes('_annotated') === annotated).map(item => ({
                                    filename: item.video_filename, videoId: item.video_filename, sizeBytes: 1,
                                    streamUrl: `${server.resolvedUrls!.local[0]}test-media/${item.video_filename}`,
                                }))}]))}}));
                    });
                }}]});
        const entry = join(temporary, 'main.cjs');
        await build({entryPoints: ['tools/media-electron.ts'], bundle: true, platform: 'node', format: 'cjs', external: ['electron'], outfile: entry});
        await server.listen();
        try {
            const app = await electron.launch({args: [entry, server.resolvedUrls!.local[0]], env: {...process.env, MEDIA_TEST: '1'}});
            try {
                const page = await app.firstWindow();
                await expect(page.locator('#bundle-ready')).toHaveText('true');
                await expect(page.locator('#ready')).toHaveText('false');
                await expect(page.locator('#error')).toBeEmpty();
                await page.locator('#mount-videos').click();
                await expect(page.locator('#ready')).toHaveText('true', {timeout: 30_000});
                await page.locator('#forward').click();
                await expect.poll(() => page.locator('video').evaluateAll(videos => videos.map(video => Math.round((video as HTMLVideoElement).currentTime * 30)))).toEqual([30, 30]);
                await page.locator('#source').click();
                await expect(page.locator('#ready')).toHaveText('true');
                await expect.poll(() => page.locator('video').evaluateAll(videos => videos.map(video => Math.round((video as HTMLVideoElement).currentTime * 30)))).toEqual([30, 30]);
                await page.locator('#back').click();
                await page.locator('#play').click();
                await expect.poll(() => page.locator('video').first().evaluate(video => (video as HTMLVideoElement).currentTime)).toBeGreaterThan(0.4);
                await expect(page.locator('#error')).toBeEmpty();
                await page.reload();
                await page.locator('#mount-videos').click();
                await expect(page.locator('#ready')).toHaveText('true');
                await expect(page.locator('#error')).toBeEmpty();
                await page.locator('#mount-videos').click();
                await expect(page.locator('#ready')).toHaveText('false');
                await page.locator('#mount-videos').click();
                await expect(page.locator('#ready')).toHaveText('true');
                await expect(page.locator('#error')).toBeEmpty();
            } finally {await app.close();}
        } finally {await server.close();}
    } finally {backend.kill();}
});

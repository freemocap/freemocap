import {test, expect, _electron as electron} from '@playwright/test';
import {build} from 'esbuild';
import {mkdtemp, readFile, readdir} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';
import {spawn} from 'node:child_process';

test('PyAV fragments play and restart in Electron without converted files', async () => {
    test.setTimeout(120_000);
    const temporary = await mkdtemp(join(tmpdir(), 'browser-stream-test-'));
    const portFile = join(temporary, 'port.txt');
    const directory = process.env.PLAYBACK_VIDEO_DIRECTORY;
    const videos = directory
        ? (await readdir(directory)).filter(name => name.endsWith('.mp4')).map(name => join(directory, name))
        : [resolve('e2e/fixtures/numbered-bframes.mp4')];
    expect(videos.length).toBeGreaterThan(0);
    const skellycam = resolve('../../skellycam');
    const backend = spawn(join(skellycam, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python'),
        ['-m', 'skellycam.tests.browser_stream_server', portFile, ...videos], {cwd: skellycam, windowsHide: true});
    let errors = '';
    backend.stderr.on('data', chunk => {errors += String(chunk);});
    backend.stdout.resume();
    try {
        await expect.poll(async () => {
            if (backend.exitCode !== null) throw new Error(errors);
            return readFile(portFile, 'utf8').catch(() => '');
        }, {timeout: 20_000}).not.toBe('');
        const port = Number(await readFile(portFile, 'utf8'));
        const entry = join(temporary, 'electron-main.cjs');
        await build({stdin: {contents: `import {app, BrowserWindow} from 'electron';
            app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
            app.whenReady().then(() => { const window = new BrowserWindow({show: false}); window.loadURL('about:blank'); });`,
            loader: 'ts'}, bundle: true, platform: 'node', external: ['electron'], outfile: entry});
        const application = await electron.launch({args: [entry]});
        try {
            const page = await application.firstWindow();
            const result = await page.evaluate(async ({port, count}) => {
                const mime = 'video/mp4; codecs="avc1.42E01F"';
                if (!MediaSource.isTypeSupported(mime)) throw new Error(`Unsupported MSE type: ${mime}`);
                const play = async (index: number, start: number): Promise<number> => {
                    const video = document.createElement('video');
                    video.muted = true;
                    document.body.append(video);
                    const media = new MediaSource();
                    const url = URL.createObjectURL(media);
                    video.src = url;
                    const abort = new AbortController();
                    try {
                        await new Promise<void>(resolve => media.addEventListener('sourceopen', () => resolve(), {once: true}));
                        const buffer = media.addSourceBuffer(mime);
                        const response = await fetch(`http://127.0.0.1:${port}/?video=${index}&start=${start}&duration=1.2`, {signal: abort.signal});
                        if (!response.ok || !response.body) throw new Error(`Stream failed: ${response.status}`);
                        const reader = response.body.getReader();
                        let bytes = 0;
                        let playing: Promise<void> | null = null;
                        for (;;) {
                            const chunk = await reader.read();
                            if (chunk.done) break;
                            bytes += chunk.value.byteLength;
                            await new Promise<void>((resolve, reject) => {
                                const done = (): void => {cleanup(); resolve();};
                                const failed = (): void => {cleanup(); reject(new Error('MSE append failed'));};
                                const cleanup = (): void => {buffer.removeEventListener('updateend', done); buffer.removeEventListener('error', failed);};
                                buffer.addEventListener('updateend', done);
                                buffer.addEventListener('error', failed);
                                buffer.appendBuffer(chunk.value);
                            });
                            if (playing === null && buffer.buffered.length > 0) playing = video.play();
                        }
                        media.endOfStream();
                        if (playing === null) throw new Error('Stream produced no playable fragments');
                        await playing;
                        await new Promise<void>((resolve, reject) => {
                            const deadline = performance.now() + 5000;
                            const check = (): void => {
                                if (video.error) reject(new Error(video.error.message));
                                else if (video.currentTime >= 0.7) resolve();
                                else if (performance.now() > deadline) reject(new Error('Video clock stalled'));
                                else setTimeout(check, 25);
                            };
                            check();
                        });
                        return bytes;
                    } finally {
                        abort.abort(); video.pause(); video.removeAttribute('src'); video.load(); video.remove(); URL.revokeObjectURL(url);
                    }
                };
                const first = await Promise.all(Array.from({length: count}, (_, index) => play(index, 0)));
                await Promise.all(Array.from({length: count}, (_, index) => play(index, 0.3)));
                await Promise.all(Array.from({length: count}, (_, index) => play(index, 0)));
                return first;
            }, {port, count: videos.length});
            expect(result.every(bytes => bytes > 0)).toBe(true);
            console.log('Concurrent video stream bytes:', result);
        } finally {await application.close();}
    } finally {backend.kill();}
});

import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer, type Server} from 'node:http';
import {execFileSync} from 'node:child_process';
import {mkdtemp, readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
test.describe.configure({mode: 'default'});

let server: Server;
let url: string;
let downloads: string[];
let directory: string;

test.beforeAll(async () => {
    directory = await mkdtemp(join(tmpdir(), 'freemocap-parquet-'));
    execFileSync(resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python'),
        ['-B', '-m', 'freemocap.tests.playback_parquet_fixture', directory], {cwd: resolve('..'), windowsHide: true});
    const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
    const worker = await build({entryPoints: ['src/services/recording/playback-parquet.worker.ts'], bundle: true,
        write: false, format: 'esm', platform: 'browser', alias: {'@': resolve('src')}});
    const entry = await build({stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
        import React, {useEffect, useState} from 'react';
        import {createRoot} from 'react-dom/client';
        import {RecordingPlaybackProvider} from './src/components/viewport3d/RecordingPlaybackProvider';
        import {useKeypointsSource} from './src/components/viewport3d/KeypointsSourceContext';
        import {PlaybackManifestSchema} from './src/services/recording/playback-data';
        import {decodePlaybackParquet} from './src/services/recording/playback-parquet';
        import {serverUrls} from './src/constants/server-urls';
        serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
        const initial = PlaybackManifestSchema.parse(${JSON.stringify(manifest)});
        const parameters = new URLSearchParams(location.search);
        const id = parameters.get('recording') ?? 'recording';
        const noop = () => {};
        let time = 0;
        const getTime = () => time;
        function Probe() {
            const source = useKeypointsSource();
            const [state, setState] = useState('empty');
            useEffect(() => source.subscribeToModelFrames(frames => {
                const frame = frames[0];
                if (!frame?.rotations || !frame.segmentOrigins || !frame.segmentLengths) {setState('empty'); return;}
                const finite = frame.segmentOrigins.data.some(Number.isFinite) && frame.rotations.worldQuaternions.some(Number.isFinite);
                const complete = frame.segmentLengths.data.every(value => value > 0) &&
                    frame.rotations.boneNames.join() === frame.segmentOrigins.names.join() &&
                    frame.rotations.boneNames.join() === frame.segmentLengths.names.join();
                setState(complete ? (finite ? 'bones:' + frame.rotations.boneNames.length : 'missing') : 'invalid');
            }), [source]);
            return <output id="frame">{state}</output>;
        }
        function App() {
            const [manifest, setManifest] = useState(initial);
            const [recordingId, setRecordingId] = useState(id);
            return <>
                <button id="first" onClick={() => {time = 0;}}>First frame</button>
                <button id="last" onClick={() => {time = 1 / 30;}}>Missing frame</button>
                <button id="switch" onClick={() => {setRecordingId('recording'); setManifest({...initial});}}>Switch recording</button>
                <RecordingPlaybackProvider recordingId={recordingId} recordingParentDirectory={null}
                    manifest={manifest} reloadManifest={() => setManifest({...manifest})} onPlaybackRun={noop}
                    mediaAvailable={true} getRecordingTime={getTime}><Probe /></RecordingPlaybackProvider>
            </>;
        }
        window.decodeFixture = async (file, descriptor) => {
            const manifest = PlaybackManifestSchema.parse(await (await fetch('/fixture/' + descriptor)).json());
            const runs = await decodePlaybackParquet(await (await fetch('/fixture/' + file)).arrayBuffer(), manifest);
            return Object.values(runs).flat().map(item => ({group: item.channel.sensor_group,
                frames: item.frame_numbers, times: item.timestamps_s}));
        };
        createRoot(document.getElementById('root')).render(<App />);
    `}, bundle: true, write: false, format: 'esm', platform: 'browser', alias: {'@': resolve('src')}});
    server = createServer(async (request, response) => {
        const path = new URL(request.url!, 'http://test').pathname;
        try {
            if (path.endsWith('/playback-parquet.worker.ts')) {
                response.setHeader('Content-Type', 'text/javascript'); response.end(worker.outputFiles[0].text);
            } else if (path === '/entry.js') {
                response.setHeader('Content-Type', 'text/javascript'); response.end(entry.outputFiles[0].text);
            } else if (path.startsWith('/fixture/')) {
                response.end(await readFile(join(directory, path.slice('/fixture/'.length))));
            } else if (path.includes('/parquet')) {
                downloads.push(path);
                if (path.includes('/stale/')) {response.writeHead(409); response.end('Recording changed; reload the playback manifest'); return;}
                if (path.includes('/slow/')) await new Promise(resolve => setTimeout(resolve, 500));
                response.setHeader('ETag', JSON.stringify(path.includes('/mismatch/') ? 'other-revision' : manifest.revision));
                response.end(path.includes('/corrupt/') ? 'invalid parquet' :
                    await readFile(join(directory, 'recording/recording_data.parquet')));
            } else if (path.includes('/window')) {
                downloads.push(path); response.writeHead(500); response.end('Obsolete window request');
            } else {
                response.setHeader('Content-Type', 'text/html');
                response.end('<div id="root"></div><script type="module" src="/entry.js"></script>');
            }
        } catch (error) {response.writeHead(500); response.end(String(error));}
    });
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    const address = server.address();
    if (!address || typeof address === 'string') throw new Error('Missing test server address');
    url = `http://127.0.0.1:${address.port}`;
});

test.afterAll(async () => {
    if (server) await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
});
test.beforeEach(() => {downloads = [];});

test('one download supplies bones, backward seeks and retained results', async ({page}) => {
    await page.goto(url);
    await expect(page.locator('#frame')).toHaveText('bones:61');
    for (let index = 0; index < 3; index++) {
        await page.locator('#last').click();
        await expect(page.locator('#frame')).toHaveText('missing');
        await page.locator('#first').click();
        await expect(page.locator('#frame')).toHaveText('bones:61');
    }
    await page.getByRole('combobox').first().selectOption('1');
    await expect(page.locator('#frame')).toHaveText('bones:61');
    expect(downloads).toEqual(['/freemocap/playback/recording/parquet']);
    await page.getByRole('button', {name: 'Reload result', exact: true}).click();
    await expect.poll(() => downloads.length).toBe(2);
    await expect(page.locator('#frame')).toHaveText('bones:61');
    expect(downloads).toHaveLength(2);
    await expect(page.getByRole('alert')).toHaveCount(0);
});

for (const recording of ['stale', 'mismatch', 'corrupt']) test(`readable ${recording} failure and recovery`, async ({page}) => {
    await page.goto(`${url}?recording=${recording}`);
    await expect(page.getByRole('alert')).not.toBeEmpty();
    await expect(page.getByRole('alert')).not.toContainText('[object Object]');
    if (recording !== 'corrupt') await expect(page.getByRole('alert')).toContainText('Recording changed');
    await page.locator('#switch').click();
    await expect(page.locator('#frame')).toHaveText('bones:61');
    await expect(page.getByRole('alert')).toHaveCount(0);
});

test('switching recording cancels the previous worker', async ({page}) => {
    await page.goto(`${url}?recording=slow`);
    await expect.poll(() => downloads.length).toBe(1);
    await page.locator('#switch').click();
    await expect(page.locator('#frame')).toHaveText('bones:61');
    expect(downloads).toEqual(['/freemocap/playback/slow/parquet', '/freemocap/playback/recording/parquet']);
    await expect(page.getByRole('alert')).toHaveCount(0);
});

test('decoder preserves native sample rates and rejects incomplete or duplicate grids', async ({page}) => {
    await page.goto(url);
    const rates = await page.evaluate(() => (window as any).decodeFixture('rates/recording/recording_data.parquet', 'rates.json'));
    expect(rates.find((item: {group: string}) => item.group === 'mocap').frames).toEqual([0, 1]);
    expect(rates.find((item: {group: string}) => item.group === 'eye').frames).toHaveLength(8);
    expect(rates.find((item: {group: string}) => item.group === 'eye').times[1]).toBe(1 / 120);
    for (const file of ['duplicate.parquet', 'incomplete.parquet']) {
        const error = await page.evaluate(async file => {
            try {await (window as any).decodeFixture(file, 'manifest.json'); return '';}
            catch (error) {return (error as Error).message;}
        }, file);
        expect(error).toMatch(/Duplicate|Incomplete/);
    }
});

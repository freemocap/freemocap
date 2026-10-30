import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import {createServer, type Server} from 'node:http';
import {execFileSync} from 'node:child_process';
import {mkdtemp, readFile, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join, resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
test.describe.configure({mode: 'default'});

let server: Server;
let url: string;
let downloads: string[];
let directory: string;
let realManifest: any = null;
const realParquet = process.env.FREEMOCAP_PLAYBACK_PARQUET;

test.beforeAll(async () => {
    directory = await mkdtemp(join(tmpdir(), 'freemocap-parquet-'));
    execFileSync(resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python'),
        ['-B', '-m', 'freemocap.tests.playback_parquet_fixture', directory], {cwd: resolve('..'), windowsHide: true});
    const manifest = JSON.parse(await readFile(join(directory, 'manifest.json'), 'utf8'));
    if (realParquet) realManifest = JSON.parse(execFileSync(resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python'),
        ['-B', '-c', 'import sys; from pathlib import Path; from freemocap.core.recording.playback_queries import playback_manifest; print(playback_manifest(Path(sys.argv[1])).model_dump_json())', realParquet],
        {cwd: resolve('..'), windowsHide: true, encoding: 'utf8', maxBuffer: 16 * 1024 * 1024}));
    const worker = await build({entryPoints: ['src/services/recording/playback-parquet.worker.ts'], bundle: true,
        write: false, format: 'esm', platform: 'browser', alias: {'@': resolve('src')}});
    const transferWorker = await build({stdin: {resolveDir: process.cwd(), loader: 'ts', contents: `
        import {ViewportFrameReceiver} from './src/components/viewport3d/viewport-frame-transfer';
        import {referencedFrameBuffers} from './src/components/viewport3d/viewport-frame-codec';
        import {workerDataStore} from './src/components/viewport3d/WorkerDataStore';
        const receiver = new ViewportFrameReceiver((message, transfers) => self.postMessage(message, transfers ?? []),
            (stream, frame) => workerDataStore.dispatch(stream, frame),
            () => referencedFrameBuffers(workerDataStore.getLatestKeypoints(), workerDataStore.getLatestModelFrames()),
            () => workerDataStore.dispatch('frameReset', null));
        workerDataStore.subscribeToKeypoints(() => receiver.scheduleRelease());
        workerDataStore.subscribeToModelFrames(() => receiver.scheduleRelease());
        self.onmessage = event => {
            if (receiver.receive(event.data)) return;
            if (event.data.type === 'probe') {
                const points = workerDataStore.getLatestKeypoints();
                self.postMessage({type: 'probe', id: event.data.id, names: points?.pointNames,
                    values: Array.from(points?.interleaved ?? []), bufferBytes: points?.interleaved.buffer.byteLength});
            } else workerDataStore.dispatch(event.data.type, event.data.data);
        };
    `}, bundle: true, write: false, format: 'esm', platform: 'browser', alias: {'@': resolve('src')}});
    const entry = await build({stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
        import React, {useCallback, useEffect, useState} from 'react';
        import {createRoot} from 'react-dom/client';
        import {RecordingPlaybackProvider} from './src/components/viewport3d/RecordingPlaybackProvider';
        import {usePlaybackController} from './src/components/playback/usePlaybackController';
        import {useKeypointsSource} from './src/components/viewport3d/KeypointsSourceContext';
        import {useRecordingSelection} from './src/components/viewport3d/RecordingSelectionContext';
        import {PlaybackManifestSchema} from './src/services/recording/playback-data';
        import {decodePlaybackParquet} from './src/services/recording/playback-parquet';
        import {ViewportFrameSender} from './src/components/viewport3d/viewport-frame-transfer';
        import {serverUrls} from './src/constants/server-urls';
        serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
        const initial = PlaybackManifestSchema.parse(new URLSearchParams(location.search).get('recording') === 'real' ? ${JSON.stringify(realManifest)} : ${JSON.stringify(manifest)});
        const parameters = new URLSearchParams(location.search);
        const id = parameters.get('recording') ?? 'recording';
        const noop = () => {};
        let time = 0;
        const getTime = () => time;
        function Probe() {
            const source = useKeypointsSource();
            const selection = useRecordingSelection();
            const [state, setState] = useState('empty');
            const [products, setProducts] = useState('empty');
            const [original, setOriginal] = useState(false);
            useEffect(() => source.subscribeToKeypoints(frame => setOriginal(frame.interleaved.some(Number.isFinite))), [source]);
            useEffect(() => source.subscribeToModelFrames(frames => {
                const frame = frames[0];
                const mapped = frame?.mappedKeypoints?.data;
                const landmarks = frame?.landmarks?.data;
                setProducts(mapped?.some(Number.isFinite) && landmarks?.some(Number.isFinite)
                    ? (mapped.some((value, index) => Number.isFinite(value) && Number.isFinite(landmarks[index]) && Math.abs(value - landmarks[index]) > 1) ? 'distinct' : 'same')
                    : 'missing');
                if (!frame?.rotations || !frame.segmentOrigins || !frame.segmentLengths) {setState('empty'); return;}
                const finite = frame.segmentOrigins.data.some(Number.isFinite) && frame.rotations.worldQuaternions.some(Number.isFinite);
                const complete = frame.segmentLengths.data.every(value => value > 0) &&
                    frame.rotations.boneNames.join() === frame.segmentOrigins.names.join() &&
                    frame.rotations.boneNames.join() === frame.segmentLengths.names.join();
                setState(complete ? (finite ? 'bones:' + frame.rotations.boneNames.length : 'missing') : 'invalid');
            }), [source]);
            return <><select aria-label="Saved run" value={selection?.runId ?? ''} onChange={event => selection?.selectRun(Number(event.target.value))}>
                {selection?.runIds.map(id => <option key={id} value={id}>{id}</option>)}</select>
                <button onClick={() => selection?.reload()}>Reload result</button><output id="cameras">{JSON.stringify(selection?.cameras)}</output><output id="frame">{state}</output><output id="products">{products}</output><output id="original">{String(original)}</output></>;
        }
        function App() {
            const [manifest, setManifest] = useState(initial);
            const [recordingId, setRecordingId] = useState(id);
            const [readyManifest, setReadyManifest] = useState(null);
            const onReady = useCallback((manifest, ready) => {
                if (ready && window.playbackReadyAt === undefined) window.playbackReadyAt = performance.now();
                setReadyManifest(current => ready ? manifest : current === manifest ? null : current);
            }, []);
            const ready = readyManifest === manifest;
            const controller = usePlaybackController({videos: [], recordingId, recordingParentDirectory: null,
                bundle: null, reloadManifest: noop, playbackReady: ready});
            return <>
                <output id="playing">{String(controller.isPlaying)}</output><button id="play" disabled={!ready} onClick={controller.handlePlayPause}>Play</button>
                <button id="first" onClick={() => {time = 0;}}>First frame</button>
                <button id="last" onClick={() => {time = 1 / 30;}}>Missing frame</button>
                <button id="switch" onClick={() => {setRecordingId('recording'); setManifest({...initial});}}>Switch recording</button>
                <RecordingPlaybackProvider recordingId={recordingId} recordingParentDirectory={null}
                    onDataReady={onReady} manifest={manifest} reloadManifest={() => setManifest({...manifest})} onPlaybackRun={noop}
                    mediaAvailable={true} getRecordingTime={getTime}><Probe /></RecordingPlaybackProvider>
            </>;
        }
        window.decodeFixture = async (file, descriptor) => {
            const manifest = PlaybackManifestSchema.parse(await (await fetch('/fixture/' + descriptor)).json());
            const runs = await decodePlaybackParquet(await (await fetch('/fixture/' + file)).arrayBuffer(), manifest);
            return Object.values(runs).flat().map(item => ({group: item.channel.sensor_group,
                frames: item.frame_numbers, times: item.timestamps_s}));
        };
        window.decodeTensorFixture = async (file, invalidLayout) => {
            const manifest = PlaybackManifestSchema.parse(await (await fetch('/fixture/tensor-manifest.json')).json());
            if (invalidLayout === 'duplicate-name') manifest.runs[0].channels[0].names[1] = manifest.runs[0].channels[0].names[0];
            if (invalidLayout === 'empty-components') manifest.runs[0].channels[0].components = {};
            if (invalidLayout === 'duplicate-channel') manifest.runs[0].channels.push(manifest.runs[0].channels[0]);
            if (invalidLayout === 'duplicate-run') manifest.runs.push(manifest.runs[0]);
            const runs = await decodePlaybackParquet(await (await fetch('/fixture/tensor-' + file + '.parquet')).arrayBuffer(), manifest);
            return Object.entries(runs).flatMap(([run_id, channels]) => channels.map(item => ({run_id: Number(run_id),
                channel: item.channel, frames: item.frame_numbers, times: item.timestamps_s,
                negativeZero: Object.is(item.values[0], -0),
                values: Array.from(item.values, value => Number.isNaN(value) ? null : value)})));
        };
        window.checkFrameTransfer = async () => {
            const worker = new Worker('/transfer-worker.js', {type: 'module'});
            const pending = new Map();
            let sequence = 0;
            const packets = [];
            const sender = new ViewportFrameSender((message, transfers) => {
                if (message.type === 'viewportFrame') packets.push({bytes: message.buffer.byteLength, layout: !!message.layout});
                worker.postMessage(message, transfers ?? []);
            });
            worker.onmessage = event => {
                sender.receive(event.data);
                if (event.data.type === 'probe') {pending.get(event.data.id)?.(event.data); pending.delete(event.data.id);}
            };
            const probe = () => new Promise(resolve => {const id = ++sequence; pending.set(id, resolve); worker.postMessage({type: 'probe', id});});
            const recording = new Float32Array(100000);
            recording.set([1, 2, 3], 30);
            const names = ['point'];
            try {
                worker.postMessage({type: 'livePresentation', data: true});
                sender.sendKeypoints({pointNames: names, interleaved: recording.subarray(30, 33)});
                const first = await probe();
                sender.sendKeypoints({pointNames: names, interleaved: new Float32Array([NaN, NaN, NaN])});
                const missing = await probe();
                sender.sendKeypoints({pointNames: names, interleaved: new Float32Array([4, 5, 6])});
                const replacement = await probe();
                sender.dispose();
                const cleared = await probe();
                return {first, missing, replacement, cleared, packets, sourceBytes: recording.byteLength,
                    sourceValues: Array.from(recording.subarray(30, 33))};
            } finally {sender.dispose(); worker.terminate();}
        };
        createRoot(document.getElementById('root')).render(<App />);
    `}, bundle: true, write: false, format: 'esm', platform: 'browser', alias: {'@': resolve('src')}});
    server = createServer(async (request, response) => {
        const path = new URL(request.url!, 'http://test').pathname;
        try {
            if (path.endsWith('/playback-parquet.worker.ts')) {
                response.setHeader('Content-Type', 'text/javascript'); response.end(worker.outputFiles[0].text);
            } else if (path === '/transfer-worker.js') {
                response.setHeader('Content-Type', 'text/javascript'); response.end(transferWorker.outputFiles[0].text);
            } else if (path === '/entry.js') {
                response.setHeader('Content-Type', 'text/javascript'); response.end(entry.outputFiles[0].text);
            } else if (path.startsWith('/fixture/')) {
                response.end(await readFile(join(directory, path.slice('/fixture/'.length))));
            } else if (path.includes('/parquet')) {
                downloads.push(path);
                if (path.includes('/real/') && realParquet) {response.setHeader('ETag', JSON.stringify(realManifest.revision)); response.end(await readFile(realParquet)); return;}
                if (path.includes('/stale/')) {response.writeHead(409); response.end('Recording changed; reload the playback manifest'); return;}
                if (path.includes('/delayed/')) await new Promise(resolve => setTimeout(resolve, 2500));
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
    if (server) await new Promise<void>((resolve, reject) => (server.close(error => error ? reject(error) : resolve()), server.closeAllConnections()));
});
test.beforeEach(({page}) => {downloads = []; page.on('pageerror', error => console.error(error));});

test('one download supplies bones, backward seeks and retained results', async ({page}) => {
    await page.goto(url);
    await expect(page.locator('#frame')).toHaveText('bones:61');
    await expect(page.locator('#products')).toHaveText('distinct');
    await expect(page.locator('#original')).toHaveText('true');
    for (let index = 0; index < 3; index++) {
        await page.locator('#last').click();
        await expect(page.locator('#frame')).toHaveText('missing');
        await expect(page.locator('#products')).toHaveText('missing');
        await expect(page.locator('#original')).toHaveText('false');
        await page.locator('#first').click();
        await expect(page.locator('#frame')).toHaveText('bones:61');
    }
    await page.getByLabel('Saved run').selectOption('1');
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

test('columnar decoder preserves declared axes across shuffled pages and rejects malformed tensors', async ({page}) => {
    await page.goto(url);
    const expected = JSON.parse(await readFile(join(directory, 'tensor-expected.json'), 'utf8'));
    const actual = await page.evaluate(() => (window as any).decodeTensorFixture('valid'));
    expect(actual).toEqual(expected.map((item: object) => ({...item, negativeZero: true})));
    for (const file of ['duplicate', 'incomplete', 'missing-column', 'units', 'component', 'name',
        'timestamp', 'inconsistent-time', 'value', 'null-frame', 'negative-frame', 'unsafe-frame',
        'null-run', 'unsafe-run', 'null-name', 'reversed-time', 'string-values']) {
        const error = await page.evaluate(async file => {
            try {await (window as any).decodeTensorFixture(file); return '';}
            catch (error) {return (error as Error).message;}
        }, file);
        expect(error, file).toMatch(/Invalid|Duplicate|Incomplete|Missing|does not match|timestamps must increase/);
    }
    for (const invalidLayout of ['duplicate-name', 'empty-components', 'duplicate-channel', 'duplicate-run']) {
        const error = await page.evaluate(async invalidLayout => {
            try {await (window as any).decodeTensorFixture('valid', invalidLayout); return '';}
            catch (error) {return (error as Error).message;}
        }, invalidLayout);
        expect(error, invalidLayout).toMatch(/Invalid|Duplicate/);
    }
});

test('real worker transfers only frame bytes and protects held live values until replacement', async ({page}) => {
    await page.goto(url);
    const result = await page.evaluate(() => (window as any).checkFrameTransfer());
    expect(result.first.values).toEqual([1, 2, 3]);
    expect(result.first.bufferBytes).toBe(12);
    expect(result.missing.values).toEqual([1, 2, 3]);
    expect(result.replacement.values).toEqual([4, 5, 6]);
    expect(result.cleared.values).toEqual([]);
    expect(result.sourceBytes).toBe(400000);
    expect(result.sourceValues).toEqual([1, 2, 3]);
    expect(result.packets).toEqual([{bytes: 12, layout: true}, {bytes: 12, layout: false}, {bytes: 12, layout: false}]);
});


test('play and keyboard wait for decoded frame zero after refresh', async ({page}) => {
    for (let attempt = 0; attempt < 2; attempt++) {
        await page.goto(`${url}?recording=delayed`);
        await expect(page.locator('#play')).toBeDisabled();
        await page.locator('body').click({position: {x: 2, y: 2}});
        await page.keyboard.press('Space');
        await expect(page.locator('#playing')).toHaveText('false');
        await expect(page.locator('#play')).toBeEnabled();
        await expect(page.locator('#frame')).toHaveText('bones:61');
        await page.locator('#play').click();
        await expect(page.locator('#playing')).toHaveText('true');
        await page.locator('#play').click();
        await expect(page.locator('#playing')).toHaveText('false');
        await page.locator('#last').click();
        await expect(page.locator('#frame')).toHaveText('missing');
        await page.locator('#first').click();
        await expect(page.locator('#frame')).toHaveText('bones:61');
    }
});


test('actual recording has frame zero and saved cameras before playback starts', async ({page}) => {
    test.skip(!realParquet, 'Set FREEMOCAP_PLAYBACK_PARQUET to a production recording');
    test.setTimeout(120_000);
    const readinessReport = process.env.FREEMOCAP_PLAYBACK_READINESS_REPORT;
    const readinessTimes: number[] = [];
    for (let attempt = 0; attempt < (readinessReport ? 6 : 2); attempt++) {
        await page.goto(`${url}?recording=real`);
        await expect(page.locator('#play')).toBeEnabled({timeout: 90_000});
        const readyAt = await page.evaluate(() => (window as any).playbackReadyAt as number);
        expect(readyAt).toBeGreaterThan(0);
        if (attempt) readinessTimes.push(readyAt);
        await expect(page.locator('#frame')).toHaveText('bones:61');
        const run = realManifest.runs.find((run: any) => run.run_id === realManifest.selected_run_id);
        const group = run.channels[0].sensor_group;
        expect(JSON.parse(await page.locator('#cameras').innerText())).toEqual(run.camera_geometry[group]);
        await page.locator('#play').click();
        await expect(page.locator('#playing')).toHaveText('true');
        await page.locator('#play').click();
        await page.locator('#last').click();
        await expect(page.locator('#frame')).toHaveText('bones:61');
        await page.locator('#first').click();
        await expect(page.locator('#frame')).toHaveText('bones:61');
        await expect(page.getByRole('alert')).toHaveCount(0);
    }
    if (readinessReport) await writeFile(readinessReport, JSON.stringify({samples_ms: readinessTimes,
        median_ms: [...readinessTimes].sort((a, b) => a - b)[Math.floor(readinessTimes.length / 2)],
        method: 'One warmup and five fresh page loads; navigation start to RecordingPlaybackProvider first ready notification, using real worker fetch/decode and first frame. Manifest is precomputed, camera video playback and full application startup excluded.'}, null, 2) + '\n');
});

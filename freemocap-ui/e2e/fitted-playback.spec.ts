/** Real saved solve -> Parquet worker -> app playback provider -> viewport worker.
 * FREEMOCAP_FITTED_PLAYBACK_PATH must name a processed Parquet with a saved fit.
 * The test reads it without changing the recording or running the solver.
 */
import {test, expect} from '@playwright/test';
import {build, type Loader} from 'esbuild';
import {createServer} from 'node:http';
import {execFileSync} from 'node:child_process';
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});
test('real fitted recording reaches the app renderer and supports seeking and independent layers', async ({page}, testInfo) => {
    test.setTimeout(180_000);
    const recording = process.env.FREEMOCAP_FITTED_PLAYBACK_PATH;
    test.skip(!recording, 'Set FREEMOCAP_FITTED_PLAYBACK_PATH to a prepared recording with a saved skeleton fit');
    const manifest = JSON.parse(execFileSync(resolve(process.platform === 'win32' ? '../.venv/Scripts/python.exe' : '../.venv/bin/python'),
        ['-B', '-c', 'import sys; from pathlib import Path; from freemocap.core.recording.playback_queries import playback_manifest; print(playback_manifest(Path(sys.argv[1])).model_dump_json())', recording!],
        {cwd: resolve('..'), windowsHide: true, maxBuffer: 50_000_000, encoding: 'utf8'}));
    const run = manifest.runs.find((r: {run_id: number}) => r.run_id === manifest.selected_run_id);
    expect(Object.keys(run.fitted_skeletons)).not.toHaveLength(0);
    const common = {bundle: true, write: false, format: 'esm' as const, platform: 'browser' as const,
        loader: {'.yaml': 'text' as Loader},
        alias: {'@': resolve('src')}, define: {'import.meta.env.DEV': 'false'}};
    const parquetWorker = await build({...common, entryPoints: ['src/services/recording/playback-parquet.worker.ts']});
    const viewportWorker = await build({...common, stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
        import './src/components/viewport3d/viewport3d.worker';
        import {getPickingEntries} from './src/components/viewport3d/renderers/PickingRegistry';
        self.addEventListener('message', event => {
            if(event.data.type !== 'test-probe') return;
            self.postMessage({type:'test-probe', data:[...getPickingEntries()].filter(([mesh, entry]) =>
                [...entry.instanceIdToName.values()].some(name => name.startsWith('Fitted '))).map(([mesh,entry]) =>
                ({count:mesh.count, labels:[...entry.instanceIdToName.values()], matrices:Array.from(mesh.instanceMatrix.array)}))});
        });
    `}});
    const entry = await build({...common, stdin: {resolveDir: process.cwd(), loader: 'tsx', contents: `
        import React from 'react'; import {createRoot} from 'react-dom/client';
        import {Provider} from 'react-redux'; import {store} from './src/store/store';
        import {RecordingPlaybackProvider} from './src/components/viewport3d/RecordingPlaybackProvider';
        import {ThreeJsCanvas, VIEWPORT_WORKER} from './src/components/viewport3d/ThreeJsCanvas';
        import {PlaybackManifestSchema} from './src/services/recording/playback-data';
        import {serverUrls} from './src/constants/server-urls';
        serverUrls.setHost(location.hostname); serverUrls.setPort(Number(location.port));
        const manifest=PlaybackManifestSchema.parse(${JSON.stringify(manifest)});
        const noop=()=>{}, time=()=>null;
        window.probe=()=>new Promise(resolve=>{const listener=e=>{if(e.data.type==='test-probe'){
            VIEWPORT_WORKER.removeEventListener('message',listener);resolve(e.data.data);}};
            VIEWPORT_WORKER.addEventListener('message',listener);VIEWPORT_WORKER.postMessage({type:'test-probe'});});
        createRoot(document.getElementById('root')).render(<Provider store={store}>
            <RecordingPlaybackProvider recordingId={manifest.recording_id} recordingParentDirectory={null}
                manifest={manifest} reloadManifest={noop} onPlaybackRun={noop} mediaAvailable={false} getRecordingTime={time}>
                <div style={{height:'700px',position:'relative'}}><ThreeJsCanvas calibration={null}/></div>
            </RecordingPlaybackProvider></Provider>);
    `}});
    const server = createServer(async (request, response) => {
        try {
            const path = new URL(request.url!, 'http://test').pathname;
            const script = path.endsWith('/playback-parquet.worker.ts') ? parquetWorker : path.endsWith('/viewport3d.worker.tsx') ? viewportWorker : path === '/entry.js' ? entry : null;
            if (script) {response.setHeader('Content-Type', 'text/javascript'); response.end(script.outputFiles[0].text);}
            else if (path.endsWith('/parquet')) {response.setHeader('ETag', JSON.stringify(manifest.revision)); response.end(await readFile(recording!));}
            else {response.setHeader('Content-Type', 'text/html'); response.end('<style>body{margin:0;background:#16202c;color:white;font:14px sans-serif}.h-full{height:100%}.w-full{width:100%}.pos-rel{position:relative}.pos-abs{position:absolute}.top-0{top:0}.left-0{left:0}.top-8{top:8px}.left-8{left:8px}.right-8{right:8px}.bottom-8{bottom:8px}.viewport-options{background:#16202cee;padding:8px}.flex{display:flex}.flex-col{flex-direction:column}.flex-row{flex-direction:row}.gap-1{gap:4px}.gap-2{gap:8px}.justify-content-space-between{justify-content:space-between}.toggle-container{width:20px;height:10px;background:#555}.toggle-container.on{background:#76dbc4}</style><div id="root"></div><script type="module" src="/entry.js"></script>');}
        } catch(error) {response.writeHead(500);response.end(String(error));}
    });
    const errors: string[] = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', msg => {if (msg.type() === 'error') errors.push(msg.text());});
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    try {
        const address = server.address(); if (!address || typeof address === 'string') throw new Error('Missing server address');
        await page.setViewportSize({width:1280,height:900});
        await page.goto(`http://127.0.0.1:${address.port}`);
        const probe = () => page.evaluate(() => (window as any).probe()) as Promise<{count:number;labels:string[];matrices:number[]}[]>;
        await expect.poll(async () => (await probe()).some(item => item.count > 0), {timeout:90_000}).toBe(true);
        const initial = await probe();
        const slider = page.getByRole('slider', {name:'Recording time'});
        const badTime = process.env.FREEMOCAP_FITTED_BAD_SAMPLE_TIME;
        if (badTime) {
            await slider.evaluate((element, value) => {
                Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(element, value);
                element.dispatchEvent(new Event('input', {bubbles: true}));
            }, badTime);
            const initialOrigins = initial.find(item => item.labels[0]?.endsWith('origin'))!.count;
            await expect.poll(async () => (await probe()).find(item => item.labels[0]?.endsWith('origin'))!.count).toBe(initialOrigins - 1);
            await expect(page.getByRole('alert')).toHaveCount(0);
        }
        await slider.focus();
        await slider.press('End');
        await expect.poll(async () => JSON.stringify(await probe())).not.toBe(JSON.stringify(initial));
        await slider.press('Home');
        await expect.poll(async () => await probe()).toEqual(initial);
        await page.locator('.viewport-options button').first().click();
        await page.getByText('Fitted skeleton', {exact:true}).click();
        await expect.poll(async () => (await probe()).every(item => item.count === 0)).toBe(true);
        await page.getByText('Fitted axes', {exact:true}).click();
        await expect.poll(async () => (await probe()).some(item => item.count > 0 && item.labels[0].endsWith('origin'))).toBe(true);
        await page.getByText('Fitted skeleton', {exact:true}).click();
        // Pull back for an inspectable whole-body screenshot; this is a camera
        // interaction, not a geometry transform or an alternative renderer.
        await page.locator('canvas').hover({position:{x:800,y:350}});
        await page.mouse.wheel(0, 700);
        await page.waitForTimeout(1500);
        await page.screenshot({path:testInfo.outputPath('fitted-app-playback.png')});
        expect(errors).toEqual([]);
        await expect(page.getByRole('alert')).toHaveCount(0);
    } finally {await page.goto('about:blank'); await new Promise<void>(resolve => server.close(()=>resolve()));}
});

/** Production UI hardware observer. Run from freemocap-ui; no server/camera ownership here. */
import {build, preview} from 'vite';
import react from '@vitejs/plugin-react';
import {_electron as electron} from '@playwright/test';
import electronPath from 'electron';
import {mkdir, writeFile, access, readFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const options = Object.fromEntries(process.argv.slice(2).map((value, index, values) =>
    value.startsWith('--') ? [value.slice(2), values[index + 1]] : []).filter(entry => entry.length));
const server = new URL(options.server);
if (!['127.0.0.1', 'localhost'].includes(server.hostname)) throw new Error('A local test server is required');
const output = path.resolve(options.output);
try { await access(output); throw new Error(`Refusing to overwrite ${output}`); }
catch (error) { if (error.code !== 'ENOENT') throw error; }
await mkdir(output, {recursive: true});
const seconds = Number(options.seconds ?? 20);
if (!(seconds >= 5 && seconds <= 120)) throw new Error('Measurement duration must be 5–120 seconds');

const workerObserver = `
(() => {
    const initial = () => ({startedMs: performance.now(), received: 0, presented: 0, sceneRenders:0, renderMs:[], bitmapMs: []});
    let values = initial();
    self.__hardwareRenderObserved = elapsed => {values.sceneRenders++; if(values.renderMs.length<20000)values.renderMs.push(elapsed);};
    const nativePost = self.postMessage.bind(self);
    self.addEventListener('message', event => {
        if (event.data?.type === 'hardware-reset') {
            event.stopImmediatePropagation();
            values = initial();
        } else if (event.data?.type === 'frame' || event.data?.type === 'decode') values.received++;
    });
    const makeBitmap = self.createImageBitmap.bind(self);
    self.createImageBitmap = async (...args) => {
        const started = performance.now();
        const bitmap = await makeBitmap(...args);
        if (values.bitmapMs.length < 20000) values.bitmapMs.push(performance.now() - started);
        return bitmap;
    };
    if (self.ImageBitmapRenderingContext) {
        const present = ImageBitmapRenderingContext.prototype.transferFromImageBitmap;
        ImageBitmapRenderingContext.prototype.transferFromImageBitmap = function(bitmap) {
            const result = present.call(this, bitmap); values.presented++; return result;
        };
    }
    setInterval(() => nativePost({type: 'hardware-observation', values: {...values,
        renderingMode: self.__hardwareRenderingMode?.(),
        durationMs: performance.now() - values.startedMs}}), 1000);
})();\n`;
function instrumentWorkers() {
    return {name: 'hardware-worker-observer', enforce: 'pre', transform(source, id) {
        if (id.replaceAll('\\', '/').endsWith('/viewport3d/ThreeJsScene.tsx')) {
            const marker = 'composerRef.current?.render();';
            if (!source.includes(marker)) throw new Error('3D scene composition observation point changed');
            return {code: source.replace(marker, `const hardwareStarted = performance.now();
try { composerRef.current?.render(); }
finally { (self as any).__hardwareRenderObserved?.(performance.now()-hardwareStarted); }`), map:null};
        }
        if (/\.worker\.tsx?(\?|$)/.test(id) && !id.includes('?worker_file')) {
            if (id.includes('viewport3d.worker')) {
                const marker = 'await newRoot.configure({';
                if (!source.includes(marker)) throw new Error('3D root configuration observation point changed');
                source = source.replace(marker, marker + `onCreated(state) {
                    (self as any).__hardwareRenderingMode = () => state.get().frameloop;
                },`);
            }
            return {code: workerObserver + source, map: null};
        }
        return null;
    }};
}
const config = {configFile: false, root, cacheDir: path.join(output, 'vite-cache'),
    plugins: [react({exclude: /\.worker\.tsx?$/}), instrumentWorkers()],
    resolve: {alias: {'@': path.join(root, 'src')}},
    worker: {format: 'es', plugins: () => [react({exclude: /\.worker\.tsx?$/}), instrumentWorkers()]},
    build: {outDir: path.join(output, 'ui-dist'), emptyOutDir: false, target: 'esnext',
        rollupOptions: {input: path.join(root, 'tools/hardware-ui.html')}},
    logLevel: 'warn'};
await build(config);
let previewServer, application, page;
const errors = [], consoleMessages = [], requests = [];
try {
    previewServer = await preview({...config, preview: {host: '127.0.0.1', port: 0}});
    const port = previewServer.httpServer.address().port;
    const main = path.join(output, 'electron-main.cjs');
    await writeFile(main, `const {app, BrowserWindow}=require('electron');
app.setPath('userData', ${JSON.stringify(path.join(output, 'electron-profile'))});
app.commandLine.appendSwitch('disable-renderer-backgrounding');
app.commandLine.appendSwitch('disable-backgrounding-occluded-windows');
app.whenReady().then(()=>{const window=new BrowserWindow({width:1440,height:1000,show:false,focusable:false,
webPreferences:{contextIsolation:true,nodeIntegration:false,backgroundThrottling:false}});
window.setIgnoreMouseEvents(true);window.showInactive();window.loadURL('about:blank');});
app.on('window-all-closed',()=>app.quit());`);
    application = await electron.launch({executablePath: electronPath, args: [main], timeout: 60000});
    page = await application.firstWindow();
    page.on('pageerror', error => errors.push(String(error)));
    page.on('console', message => consoleMessages.push({type: message.type(), text: message.text()}));
    page.on('request', request => {if(['POST','PUT','DELETE','PATCH'].includes(request.method()))
        requests.push({url:request.url(),method:request.method(),body:request.postData()});});
    await page.addInitScript(({serverHost, serverPort}) => {
        localStorage.setItem('freemocap:serverHost', JSON.stringify(serverHost));
        localStorage.setItem('freemocap:serverPort', JSON.stringify(serverPort));
        localStorage.setItem('freemocap:autoLaunchServer', 'false');
        localStorage.setItem('freemocap:autoConnectWs', 'true');
        sessionStorage.setItem('freemocap.welcomeShown', 'true');
        const workers = [];
        const probe = window.__hardwareProbe = {frames: [], decodedFrames: [], canvasSubmissions: [],
            samples: {}, workers: {}, interactions:[], decodeActive: 0, decodeMaximum: 0, reactCommits: 0, longTasks: [], rafTimes: [],
            sample(label, value) {(this.samples[label] ??= []).push(value);},
            reset() {this.frames=[];this.decodedFrames=[];this.canvasSubmissions=[];this.samples={};
                this.workers={};this.reactCommits=0;this.longTasks=[];this.rafTimes=[];this.decodeMaximum=this.decodeActive;
                workers.forEach(worker=>worker.postMessage({type:'hardware-reset'}));this.startedMs=performance.now();}};
        window.__REACT_DEVTOOLS_GLOBAL_HOOK__ = {supportsFiber: true, inject: () => 1,
            onCommitFiberRoot() {probe.reactCommits++;}, onCommitFiberUnmount() {}};
        for(const type of ['click','change','keydown'])document.addEventListener(type,event=>
            probe.interactions.push({type, trusted:event.isTrusted, atMs:performance.now(),
                target:event.target?.getAttribute?.('aria-label') ?? event.target?.tagName}),true);
        const NativeWorker = window.Worker;
        window.Worker = class extends NativeWorker {
            constructor(url, options) {
                super(url, options); this.hardwareId=workers.length; workers.push(this);
                this.addEventListener('message', event => {
                    if(event.data?.type==='hardware-observation') {
                        event.stopImmediatePropagation();
                        probe.workers[this.hardwareId]={url:String(url),cameraId:this.hardwareCameraId,
                            ...event.data.values};
                    }
                });
            }
        };
        new PerformanceObserver(list=>probe.longTasks.push(...list.getEntries().map(item=>
            ({startMs:item.startTime,durationMs:item.duration})))).observe({type:'longtask'});
        function tick(now) {probe.rafTimes.push(now); requestAnimationFrame(tick);}
        requestAnimationFrame(tick);
    }, {serverHost: server.hostname, serverPort: Number(server.port)});
    await page.goto(`http://127.0.0.1:${port}/tools/hardware-ui.html#/streaming`);
    if (options['idle-only']) {
        await page.waitForFunction(() => Object.values(window.__hardwareProbe?.workers ?? {}).some(worker => worker.renderingMode), null, {timeout:30000});
        await page.setViewportSize({width:1300,height:900});
    } else {
        await page.waitForFunction(() => window.__hardwareProbe?.decodedFrames.length >= 30, null, {timeout: 90000});
        await page.getByRole('button', {name:'Frame the subject', exact:true}).click();
    }
    await page.waitForTimeout(5000);
    await page.evaluate(() => window.__hardwareProbe.reset());
    await page.waitForTimeout(seconds * 1000);
    const measurements = await page.evaluate(() => ({...window.__hardwareProbe,
        endedMs: performance.now(), visibility: document.visibilityState, cameraState:window.__hardwareProbe.readCameraState(),
        channels:window.__hardwareProbe.readChannelStats(),
        canvasSizes: [...document.querySelectorAll('canvas')].map(c=>({width:c.width,height:c.height,
            displayedWidth:c.clientWidth,displayedHeight:c.clientHeight}))}));
    await page.screenshot({path: path.join(output, 'application.png')});
    await writeFile(path.join(output, 'ui-measurements.json'), JSON.stringify({buildMode:'production',
        instrumentation:'test entry and worker observer', server:server.href, errors, requests, measurements,
        gpu:await application.evaluate(({app})=>app.getGPUFeatureStatus())}, null, 2));
    if (errors.length) throw new Error(`UI produced ${errors.length} uncaught errors`);
    const scene = Object.values(measurements.workers).find(worker => worker.url.includes('viewport3d.worker'));
    if (scene?.renderingMode !== 'demand') throw new Error(`3D viewport switched to ${scene?.renderingMode} rendering`);
    if (options['idle-only'] && scene.sceneRenders > 2) throw new Error('Idle 3D viewport kept redrawing');
    if (!options['idle-only'] && Object.values(measurements.workers).filter(worker=>worker.cameraId && worker.presented>0).length !== measurements.cameraState.length)
        throw new Error('Not every camera renderer presented images');
    if (measurements.rafTimes.length < measurements.frames.length * 0.8)
        throw new Error('Browser animation is throttled; this is not a valid foreground UI measurement');
    if (options['expected-configs']) {
        const expected=JSON.parse(await readFile(options['expected-configs'],'utf8'));
        for(const camera of measurements.cameraState)for(const field of ['exposure','exposure_mode','rotation','framerate'])
            for(const kind of ['actualConfig','desiredConfig'])if(camera[kind][field]!==expected[camera.id][field])
                throw new Error(`UI ${kind} ${field} differs from running camera ${camera.id}`);
    }
} finally {
    await writeFile(path.join(output, 'console.json'), JSON.stringify({errors, requests, messages:consoleMessages}, null, 2));
    if (page) await page.screenshot({path:path.join(output,'last-state.png')}).catch(()=>{});
    if (application) await application.close();
    if (previewServer) await new Promise(resolve=>previewServer.httpServer.close(resolve));
}

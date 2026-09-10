import {test, expect} from '@playwright/test';
import {build} from 'esbuild';
import path from 'node:path';

test.use({channel: process.env.PLAYWRIGHT_CHANNEL});

test('child auto-connect survives provider initialization and delivers calibration progress', async ({page}) => {
    const errors: string[] = [];
    page.on('pageerror', error => {errors.push(error.message); console.error(error.message);});
    await page.setContent('<div id="root"></div><output id="result"></output>');
    const bundle = await build({
        stdin: {resolveDir: path.resolve('.'), loader: 'tsx', contents: `
            import React, {useEffect} from 'react';
            import {createRoot} from 'react-dom/client';
            import {encode} from 'cbor-x';
            import {ServerContextProvider, useServer} from './src/services/server/ServerContextProvider';
            import {connections} from '@/services/server/server-helpers/websocket-connection';
            import {store} from '@/store';
            import {applyTaskSnapshot} from './src/services/server/task-progress';
            function assert(value: boolean, message: string): void {if (!value) throw new Error(message);}
            let client: ReturnType<typeof useServer>;
            function AutoConnect(): null {
                client = useServer();
                useEffect(() => {client.connect();}, []);
                return null;
            }
            const root = createRoot(document.getElementById('root')!);
            root.render(<ServerContextProvider><AutoConnect /></ServerContextProvider>);
            setTimeout(() => {
                assert(connections.length === 1 && connections[0].connected, 'Initial auto-connect request was lost');
                const task = {task_id: 'calibration:task', task_type: 'calibration', revision: 1, status: 'running',
                    recording: {base_directory: '/test', recording_name: 'recording', full_path: '/test/recording'},
                    progress: {phase: 'collecting_camera_output', progress_fraction: .5, detail: 'Collecting observations'},
                    cameras: [], created_at: '2026-09-10T00:00:00Z', updated_at: '2026-09-10T00:00:00Z'};
                const snapshot = {recording_owners: [], server_instance_id: '10000000-0000-4000-8000-000000000000', revision: 1, tasks: [task]};
                const send = (snapshot: object): void => connections[0].emit('message', {data: Uint8Array.from(encode({kind: 'progress', version: 0, timestamp: 1, sequence: 0, snapshot})).buffer});
                send(snapshot);
                assert(store.actions.some((a) => a.payload?.tasks?.[0]?.progress.progress_fraction === .5), 'Progress did not reach the pipeline store');
                const second = {...snapshot, revision: 2, tasks: [{...task, revision: 2, progress: {...task.progress, detail: 'Solving camera 2'}}]};
                send(second);
                assert(store.actions.some((a) => a.payload?.tasks?.[0]?.progress.detail === 'Solving camera 2'), 'Detail-only update was discarded');
                client.disconnect();
                client.connect();
                const count = store.actions.filter((a) => a.type === 'snapshot').length;
                send(second);
                assert(store.actions.filter((a) => a.type === 'snapshot').length === count, 'Repeated snapshot caused another update');
                const completed = {...snapshot, revision: 3, tasks: [{...task, revision: 3, status: 'complete', progress: {...task.progress, phase: 'complete', progress_fraction: 1}}]};
                applyTaskSnapshot(completed, store.getState().pipelines, store.dispatch);
                send(completed);
                assert(store.actions.some((a) => a.payload?.tasks?.[0]?.status === 'complete'), 'Completion was lost');
                assert(store.actions.filter((a) => a.type === 'load-calibration').length === 1, 'HTTP-first completion did not load calibration exactly once');
                root.unmount();
                assert(!connections[0].connected, 'Unmount left the connection open');
                document.getElementById('result')!.textContent = 'passed';
            }, 100);
        `},
        bundle: true, write: false, format: 'esm', alias: {'@': path.resolve('src')},
        plugins: [{name: 'provider-boundaries', setup(builder) {
            builder.onResolve({filter: /^@\/store(?:\/.*)?$/}, args => ({path: args.path, namespace: 'store-stub'}));
            builder.onLoad({filter: /.*/, namespace: 'store-stub'}, () => ({loader: 'ts', contents: `
                                const state = {pipelines: {recordingOwners: [], serverInstanceId: null as string|null, registryRevision: -1, activePipelines: {}}};
                export const store = {actions: [] as object[], getState: () => state, dispatch(action): void {
                    store.actions.push(action);
                    if(action.type === 'snapshot') state.pipelines = {recordingOwners: action.payload.recording_owners, serverInstanceId: action.payload.server_instance_id, registryRevision: action.payload.revision,
                        activePipelines: Object.fromEntries(action.payload.tasks.map(task => [task.task_id, {phase: task.progress.phase}]))};
                }};
                export const PipelineType = {CALIBRATION: 'calibration', MOCAP: 'mocap'};
                export const PipelinePhase = {COMPLETE: 'complete', FAILED: 'failed', COLLECTING: 'collecting', SETTING_UP: 'setting_up'};
                export const recordingPlaybackInvalidated = (payload: object) => ({type: "invalidate-playback", payload}); export const taskSnapshotReceived = (payload: object) => ({type: 'snapshot', payload});
                export const serverStateReceived = (payload: object) => ({type: 'state', payload});
                export const wsConnectionChanged = (payload: object) => ({type: 'connection', payload});
                export const serverDisconnected = () => ({type: 'disconnected'});
                export const modelsReceived = () => ({}), conventionReceived = () => ({}), camerasReceived = () => ({});
                export const loadCalibrationForRecording = () => ({type: 'load-calibration'}), fetchPlaybackBundle = () => ({type: 'load-playback'});
                export const splitParentAndName = () => null;
            `}));
            builder.onResolve({filter: /^@\/services$/}, () => ({path: 'services', namespace: 'services-stub'}));
            builder.onLoad({filter: /.*/, namespace: 'services-stub'}, () => ({loader: 'ts', contents: `
                export const serverUrls = {getWebSocketUrl: () => 'ws://test', setHost(): void {}, setPort(): void {}};
            `}));
            builder.onLoad({filter: /websocket-connection\.ts$/}, () => ({loader: 'ts', contents: `
                export const ConnectionState = {CONNECTED: 'connected', DISCONNECTED: 'disconnected', FAILED: 'failed'};
                export const connections: WebSocketConnection[] = [];
                export class WebSocketConnection {
                    connected = false;
                    listeners = new Map<string, Set<(value: unknown) => void>>();
                    constructor() {connections.push(this);}
                    on(event: string, cb: (value: unknown) => void): void {if (!this.listeners.has(event)) this.listeners.set(event, new Set()); this.listeners.get(event)!.add(cb);}
                    off(event: string, cb: (value: unknown) => void): void {this.listeners.get(event)?.delete(cb);}
                    emit(event: string, value: unknown): void {this.listeners.get(event)?.forEach(cb => cb(value));}
                    connect(): void {this.connected = true; this.emit('state-change', ConnectionState.CONNECTED);}
                    disconnect(): void {this.connected = false; this.emit('state-change', ConnectionState.DISCONNECTED);}
                    send(): void {} updateUrl(): void {} getState(): string {return this.connected ? 'connected' : 'disconnected';}
                }
            `}));
            builder.onLoad({filter: /(?:frame-processor|canvas-manager|framerate-store|log-store)\.ts$/}, () => ({loader: 'ts', contents: `
                import {z} from 'zod';
                export const LogRecordSchema = z.object({});
                class Service {start(): void {} dispose(): void {} close(): void {} clear(): void {} reset(): void {} terminateAllWorkers(): void {}}
                export {Service as FrameProcessor, Service as CanvasManager, Service as FramerateStore, Service as LogStore};
            `}));
        }}],
    });
    await page.addScriptTag({content: bundle.outputFiles[0].text, type: 'module'});
    await expect(page.locator('#result')).toHaveText('passed');
    expect(errors).toEqual([]);
});



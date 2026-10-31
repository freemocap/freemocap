// Test-only instrumentation around the real application and its production workers.
// This entry is never imported by the normal application build.
import {TransportService} from '../src/services/server/transport/TransportService';
import {FrameProcessor} from '../src/services/server/server-helpers/frame-processor/frame-processor';
import {CanvasManager} from '../src/services/server/server-helpers/canvas-manager';
import {store} from '../src/store';

const probe: any = (window as any).__hardwareProbe;
let latestFrame: any;
probe.readChannelStats = () => ['trackers', 'instances'].flatMap(collection =>
    (latestFrame?.[collection] ?? []).flatMap((source:any) => source.channels.filter((channel:any) =>
        !channel.camera_id).map((channel:any) => {
        const values = new Float32Array(channel.data.slice().buffer);
        return {collection, modelId:source.model_id, kind:channel.kind, rows:values.length/channel.columns.length,
            components:channel.columns.map((name:string, offset:number) => {
                let minimum=Infinity, maximum=-Infinity, finiteCount=0;
                for(let index=offset;index<values.length;index+=channel.columns.length)if(Number.isFinite(values[index])) {
                    finiteCount++;minimum=Math.min(minimum,values[index]);maximum=Math.max(maximum,values[index]);
                }
                return {name,finiteCount,minimum:finiteCount?minimum:null,maximum:finiteCount?maximum:null};
            })};
    })));
probe.readCameraState = () => store.getState().cameras.cameras.map(camera => ({id:camera.id,
    actualConfig:camera.actualConfig, desiredConfig:camera.desiredConfig}));
function timedMethod(target: any, name: string, label: string) {
    const original = target[name];
    if (typeof original !== 'function') throw new Error(`Missing instrumented method ${name}`);
    target[name] = function (...args: any[]) {
        const started = performance.now();
        try { return original.apply(this, args); }
        finally { probe.sample(label, performance.now() - started); }
    };
}
timedMethod(TransportService.prototype, 'dispatchBytes', 'messageDispatchMs');
timedMethod(TransportService.prototype, 'handleFrame', 'frameDispatchMs');
const handleFrame = (TransportService.prototype as any).handleFrame;
(TransportService.prototype as any).handleFrame = function (frame: any) {
    latestFrame = frame;
    probe.frames.push({arrivalMs: performance.now(), frameNumber: frame.frame_number,
        diagnosticsPresent: frame.diagnostics != null, trackerCount: frame.trackers.length,
        instanceCount: frame.instances.length});
    return handleFrame.call(this, frame);
};
const processFrame = FrameProcessor.prototype.processFramePayload;
FrameProcessor.prototype.processFramePayload = async function (payload: ArrayBuffer) {
    const started = performance.now();
    probe.decodeActive++;
    probe.decodeMaximum = Math.max(probe.decodeMaximum, probe.decodeActive);
    try {
        const result = await processFrame.call(this, payload);
        probe.sample('decodeRoundTripMs', performance.now() - started);
        for (const frame of result?.frames ?? []) {
            probe.decodedFrames.push({cameraId: frame.cameraId, frameNumber: frame.frameNumber,
                width: frame.width, height: frame.height, completedMs: performance.now()});
        }
        return result;
    } finally { probe.decodeActive--; }
};
const sendFrame = CanvasManager.prototype.sendFrameToWorker;
CanvasManager.prototype.sendFrameToWorker = function (cameraId, ...args) {
    const worker = (this as any).workers.get(cameraId)?.worker;
    if (worker) worker.hardwareCameraId = cameraId;
    const accepted = sendFrame.call(this, cameraId, ...args);
    probe.canvasSubmissions.push({cameraId, accepted, submittedMs: performance.now()});
    return accepted;
};

await import('../src/main');

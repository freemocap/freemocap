import {DecoderCommand, DecoderReply, type DecoderRequest, type DecoderResponse} from '../../src/services/recording/media-decoder-protocol';
import {validateVideoGroup} from '../../src/services/recording/synchronized-video-group';
import {FrameLookahead} from '../../src/services/recording/frame-lookahead';

class DecoderClient {
    private readonly worker = new Worker(new URL('../../src/services/recording/media-decoder.worker.ts', import.meta.url), {type: 'module'});
    private pending: {resolve: (value: DecoderResponse) => void; reject: (error: Error) => void} | null = null;
    constructor() {
        this.worker.onmessage = (event: MessageEvent<DecoderResponse>): void => {
            const pending = this.pending; this.pending = null;
            if (!pending) {if (event.data.kind === DecoderReply.Frame) event.data.bitmap.close(); return;}
            if (event.data.kind === DecoderReply.Error) pending.reject(new Error(event.data.message));
            else pending.resolve(event.data);
        };
        this.worker.onerror = (event): void => {this.pending?.reject(new Error(event.message)); this.pending = null;};
    }
    request(message: DecoderRequest): Promise<DecoderResponse> {
        if (this.pending) throw new Error('Concurrent decoder requests are not allowed');
        return new Promise((resolve, reject) => {this.pending = {resolve, reject}; this.worker.postMessage(message);});
    }
    close(): void {this.worker.terminate(); this.pending?.reject(new Error('Video group closed')); this.pending = null;}
}

const file = document.querySelector<HTMLInputElement>('#file')!;
const ordinal = document.querySelector<HTMLInputElement>('#ordinal')!;
const button = document.querySelector<HTMLButtonElement>('#read')!;
const play = document.querySelector<HTMLButtonElement>('#play')!;
const pause = document.querySelector<HTMLButtonElement>('#pause')!;
const status = document.querySelector<HTMLElement>('#status')!;
const container = document.querySelector<HTMLElement>('#frames')!;
let clients: DecoderClient[] = [];
let canvases: HTMLCanvasElement[] = [];
let generation = 0;
let frameCount = 0;
let fps = 0;
let playbackGeneration = 0;
let animation = 0;
type Frames = Extract<DecoderResponse, {kind: DecoderReply.Frame}>[];
let lookahead: FrameLookahead<Frames> | null = null;
function release(frames: Frames): void {frames.forEach(frame => frame.bitmap.close());}
function closeGroup(): void {
    playbackGeneration++; window.clearTimeout(animation);
    const buffer = lookahead; lookahead = null;
    if (buffer) void buffer.close().catch((error: unknown) => {status.textContent = `ERROR: ${String(error)}`;});
    clients.forEach(client => client.close()); clients = [];
    button.disabled = true; play.disabled = true; pause.disabled = true;
}

async function loadFrames(target: number): Promise<Frames> {
    const results = await Promise.allSettled(clients.map(client => client.request({kind: DecoderCommand.Read, ordinal: target})));
    const frames = results.flatMap(result => result.status === 'fulfilled' && result.value.kind === DecoderReply.Frame ? [result.value] : []);
    const failure = results.find(result => result.status === 'rejected');
    if (failure?.status === 'rejected' || frames.length !== results.length || frames.some(frame => frame.ordinal !== target)) {
        release(frames);
        throw failure?.status === 'rejected' ? failure.reason : new Error('Incomplete synchronized frame');
    }
    return frames;
}

function present(frames: Frames): void {
    const contexts = canvases.map(canvas => {
        const context = canvas.getContext('2d'); if (!context) throw new Error('Canvas unavailable'); return context;
    });
    frames.forEach((frame, index) => {
        const canvas = canvases[index];
        if (canvas.width !== frame.bitmap.width) canvas.width = frame.bitmap.width;
        if (canvas.height !== frame.bitmap.height) canvas.height = frame.bitmap.height;
        contexts[index].drawImage(frame.bitmap, 0, 0);
        canvas.dataset.ordinal = String(frame.ordinal);
    });
    ordinal.value = String(frames[0].ordinal);
}

file.onchange = (): void => {
    closeGroup();
    const current = ++generation;
    const selected = Array.from(file.files ?? []);
    container.replaceChildren(); canvases = [];
    if (!selected.length) return;
    status.textContent = 'Validating synchronized video group…';
    clients = selected.map(() => new DecoderClient());
    const budgetBytes = Math.floor(32 * 1024 * 1024 / selected.length);
    void Promise.all(clients.map(async (client, index) => {
        const response = await client.request({kind: DecoderCommand.Open, file: selected[index], budgetBytes});
        if (response.kind !== DecoderReply.Ready) throw new Error('Expected decoder readiness');
        return {name: selected[index].name, ...response};
    })).then(grids => {
        if (current !== generation) return;
        frameCount = validateVideoGroup(grids);
        // One estimate paces the whole group; per-file rates never determine frame correspondence.
        fps = grids[0].fps; ordinal.max = String(frameCount - 1);
        canvases = selected.map((video, index) => {
            const pane = document.createElement('figure');
            const caption = document.createElement('figcaption'); caption.textContent = video.name;
            const canvas = document.createElement('canvas'); canvas.id = index === 0 ? 'frame' : `frame-${index}`;
            canvas.style.maxWidth = '100%'; pane.append(caption, canvas); container.append(pane); return canvas;
        });
        status.textContent = `Ready: ${selected.length} videos, ${frameCount} frames, playback pace ${fps} FPS`;
        button.disabled = false; play.disabled = false;
    }).catch((error: unknown) => {
        if (current !== generation) return;
        closeGroup(); status.textContent = `ERROR: ${String(error)}`;
    });
};
play.onclick = (): void => {
    const start = ordinal.valueAsNumber;
    if (!Number.isSafeInteger(start) || start < 0 || start >= frameCount) {status.textContent = 'ERROR: Invalid starting frame'; return;}
    const token = ++playbackGeneration;
    button.disabled = true; play.disabled = true; pause.disabled = true;
    status.textContent = 'Preloading video group…';
    void (async () => {
        const first = await loadFrames(start);
        try {
            if (token !== playbackGeneration) return;
            const groupBytes = first.reduce((sum, frame) => sum + frame.bitmap.width * frame.bitmap.height * 4, 0);
            // Include a displayed group and one load in flight in the presentation-buffer budget.
            const capacity = Math.min(Math.ceil(fps * 0.5), Math.floor(256 * 1024 * 1024 / groupBytes) - 2);
            if (capacity < 1) throw new Error('Video group exceeds the prototype lookahead memory budget');
            const buffer = new FrameLookahead({start: start + 1, end: frameCount, capacity, load: loadFrames, release});
            lookahead = buffer;
            await buffer.fill();
            if (token !== playbackGeneration) return;
            present(first);
            status.textContent = `Playing — up to ${capacity} frames ahead`;
            pause.disabled = false;
            let deadline = performance.now() + 1000 / fps;
            let stalled = false;
            const fail = (error: unknown): void => {
                if (token !== playbackGeneration) return;
                closeGroup(); status.textContent = `ERROR: ${String(error)}`;
            };
            const tick = (now: number): void => {
                if (token !== playbackGeneration) return;
                try {
                    if (now >= deadline) {
                        const frames = buffer.take();
                        if (frames) {
                            try {present(frames);} finally {release(frames);}
                            deadline = stalled || now - deadline > 1000 / fps ? now + 1000 / fps : deadline + 1000 / fps;
                            if (stalled) {status.textContent = 'Playing'; stalled = false;}
                            void buffer.fill().catch(fail);
                        } else if (buffer.finished) {
                            status.textContent = 'Playback complete'; button.disabled = false; play.disabled = false; pause.disabled = true;
                            return;
                        } else if (!stalled) {stalled = true; status.textContent = 'Buffering video group…';}
                    }
                    animation = window.setTimeout(() => tick(performance.now()), stalled ? 1000 / fps : Math.max(1, deadline - performance.now()));
                } catch (error) {fail(error);}
            };
            animation = window.setTimeout(() => tick(performance.now()), 1000 / fps);
        } finally {release(first);}
    })().catch((error: unknown) => {if (token === playbackGeneration) {closeGroup(); status.textContent = `ERROR: ${String(error)}`;}});
};
pause.onclick = (): void => {
    const token = ++playbackGeneration; window.clearTimeout(animation); pause.disabled = true;
    const buffer = lookahead; lookahead = null;
    void (buffer?.close() ?? Promise.resolve()).then(() => {
        if (token !== playbackGeneration) return;
        status.textContent = 'Paused'; button.disabled = false; play.disabled = false;
    }).catch((error: unknown) => {if (token === playbackGeneration) {closeGroup(); status.textContent = `ERROR: ${String(error)}`;}});
};
button.onclick = (): void => {
    const target = ordinal.valueAsNumber;
    if (!Number.isSafeInteger(target) || target < 0 || target >= frameCount) {status.textContent = 'ERROR: Frame is outside the group'; return;}
    button.disabled = true; play.disabled = true;
    const current = generation;
    void Promise.allSettled(clients.map(client => client.request({kind: DecoderCommand.Read, ordinal: target}))).then(results => {
        const frames = results.flatMap(result => result.status === 'fulfilled' && result.value.kind === DecoderReply.Frame ? [result.value] : []);
        try {
            if (current !== generation) return;
            const failure = results.find(result => result.status === 'rejected');
            if (failure?.status === 'rejected') throw failure.reason;
            if (frames.length !== canvases.length || frames.some(frame => frame.ordinal !== target)) throw new Error('Incomplete synchronized frame');
            present(frames);
            status.textContent = JSON.stringify({ordinal: target, cacheHit: frames.every(frame => frame.cacheHit),
                restarts: Math.max(...frames.map(frame => frame.restarts)), videos: frames.length});
            button.disabled = false; play.disabled = false;
        } catch (error) {closeGroup(); status.textContent = `ERROR: ${String(error)}`;}
        finally {frames.forEach(frame => frame.bitmap.close());}
    });
};
window.addEventListener('pagehide', closeGroup);

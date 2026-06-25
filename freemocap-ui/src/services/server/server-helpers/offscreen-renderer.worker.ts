export const workerCode = `
let offscreenCanvas;
let ctx;
/** @type {{ bitmap: ImageBitmap, frameNumber: number, rafCycleStartMs: number, frameReceivedAt: number } | null} */
let pendingFrame = null;
let isRendering = false;
let lastRenderTime = 0;
let cameraId = '';
let stats = {
    framesRendered: 0,
    framesDropped: 0,
    totalRenderTime: 0
};

let renderLoopScheduled = false;

function scheduleRenderLoop() {
    if (!renderLoopScheduled) {
        renderLoopScheduled = true;
        requestAnimationFrame(renderLoop);
    }
}

self.onmessage = (e) => {
    const { type } = e.data;
    
    switch (type) {
        case 'init':
            initCanvas(e.data);
            break;
            
        case 'frame':
            handleFrame(e.data);
            break;
            
        case 'getStats':
            self.postMessage({ type: 'stats', stats });
            break;
    }
};

function initCanvas(data) {
    offscreenCanvas = data.canvas;
    cameraId = typeof data.cameraId === 'string' ? data.cameraId : '';
    
    ctx = offscreenCanvas.getContext('bitmaprenderer');

    self.postMessage({ type: 'initialized' });
}

function handleFrame(data) {
    const bitmap = data.bitmap;
    const frameNumber = typeof data.frameNumber === 'number' ? data.frameNumber : -1;
    const rafCycleStartMs = typeof data.rafCycleStartMs === 'number' ? data.rafCycleStartMs : 0;
    const mainSentAtMs = typeof data.mainSentAtMs === 'number' ? data.mainSentAtMs : 0;
    const frameReceivedAt = performance.now();
    const receiveLagMs = mainSentAtMs > 0 ? Math.max(0, frameReceivedAt - mainSentAtMs) : 0;
    
    if (!bitmap || bitmap.width <= 0 || bitmap.height <= 0) {
        console.error('Invalid bitmap dimensions:', bitmap?.width, bitmap?.height);
        if (bitmap) bitmap.close();
        return;
    }
    
    if (offscreenCanvas.width !== bitmap.width || offscreenCanvas.height !== bitmap.height) {
        offscreenCanvas.width = bitmap.width;
        offscreenCanvas.height = bitmap.height;
    }
    
    if (pendingFrame) {
        pendingFrame.bitmap.close();
        stats.framesDropped++;
    }
    pendingFrame = { bitmap, frameNumber, rafCycleStartMs, frameReceivedAt, receiveLagMs };

    scheduleRenderLoop();
}

function renderLoop() {
    renderLoopScheduled = false;
    const rafCallbackAt = performance.now();
    const startTime = performance.now();
    
    if (pendingFrame && !isRendering) {
        isRendering = true;
        
        const frame = pendingFrame;
        pendingFrame = null;
        const fn = frame.frameNumber;
        const rafAt = frame.rafCycleStartMs;
        const workerRafWaitMs = Math.max(0, rafCallbackAt - frame.frameReceivedAt);
        const receiveLagMs = typeof frame.receiveLagMs === 'number' ? frame.receiveLagMs : 0;
        
        ctx.transferFromImageBitmap(frame.bitmap);
        frame.bitmap.close();
        
        stats.framesRendered++;
        const renderTime = performance.now() - startTime;
        stats.totalRenderTime += renderTime;
        
        if (renderTime > 16.67) {
            console.warn('Slow frame: ' + renderTime.toFixed(2) + 'ms');
        }
        
        isRendering = false;
        lastRenderTime = performance.now();

        self.postMessage({
            type: 'renderAck',
            cameraId,
            frameNumber: fn,
            renderMs: renderTime,
            rafCycleStartMs: rafAt,
            workerRafWaitMs,
            receiveLagMs,
        });

        if (pendingFrame) {
            scheduleRenderLoop();
        }
    }
}
`;

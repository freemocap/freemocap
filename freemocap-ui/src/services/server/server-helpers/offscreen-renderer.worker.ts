export const workerCode = `
let offscreenCanvas;
let ctx;
let pendingFrame = null;
let isRendering = false;
let lastRenderTime = 0;
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
    
    // Use ImageBitmapRenderingContext - fastest for bitmap streaming
    ctx = offscreenCanvas.getContext('bitmaprenderer');

    self.postMessage({ type: 'initialized' });
}

function handleFrame(data) {
    const bitmap = data.bitmap;
    
    // Validate bitmap dimensions
    if (!bitmap || bitmap.width <= 0 || bitmap.height <= 0) {
        console.error('Invalid bitmap dimensions:', bitmap?.width, bitmap?.height);
        if (bitmap) bitmap.close();
        return;
    }
    
    // Resize canvas to match bitmap dimensions if they differ
    // This handles rotation changes and different camera resolutions
    if (offscreenCanvas.width !== bitmap.width || offscreenCanvas.height !== bitmap.height) {
        offscreenCanvas.width = bitmap.width;
        offscreenCanvas.height = bitmap.height;
        // Resizing automatically clears the canvas, preventing old frame artifacts
    }
    
    // Frame dropping strategy: keep only latest frame
    if (pendingFrame) {
        pendingFrame.close(); // Clean up skipped frame
        stats.framesDropped++;
    }
    pendingFrame = bitmap;

    // Wake up the render loop if it is idle.
    scheduleRenderLoop();
}

function renderLoop() {
    renderLoopScheduled = false;
    const startTime = performance.now();
    
    if (pendingFrame && !isRendering) {
        isRendering = true;
        
        const frame = pendingFrame;
        pendingFrame = null;
        
        // transferFromImageBitmap detaches the bitmap (ownership transferred to canvas).
        // Explicit close() afterwards as a safety net for browser edge cases.
        ctx.transferFromImageBitmap(frame);
        frame.close();
        
        // Update stats
        stats.framesRendered++;
        const renderTime = performance.now() - startTime;
        stats.totalRenderTime += renderTime;
        
        // Warn if frame took too long
        if (renderTime > 16.67) {
            console.warn(\`Slow frame: \${renderTime.toFixed(2)}ms\`);
        }
        
        isRendering = false;
        lastRenderTime = performance.now();

        // If another frame arrived while we were rendering, keep going.
        if (pendingFrame) {
            scheduleRenderLoop();
        }
    }
}
`;

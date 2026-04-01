export const workerCode = `
let offscreenCanvas;
let ctx;
let pendingFrame = null;
let isRendering = false;
let stats = {
    framesRendered: 0,
    framesDropped: 0,
    totalRenderTime: 0
};

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
    ctx = offscreenCanvas.getContext('bitmaprenderer');
    renderLoop();
    self.postMessage({ type: 'initialized' });
}

function handleFrame(data) {
    const bitmap = data.bitmap;
    
    if (!bitmap || bitmap.width <= 0 || bitmap.height <= 0) {
        console.error('Invalid bitmap dimensions:', bitmap?.width, bitmap?.height);
        if (bitmap) bitmap.close();
        return;
    }
    
    // Resize canvas if needed
    if (offscreenCanvas.width !== bitmap.width || offscreenCanvas.height !== bitmap.height) {
        offscreenCanvas.width = bitmap.width;
        offscreenCanvas.height = bitmap.height;
    }
    
    // Drop old frame if still pending
    if (pendingFrame) {
        pendingFrame.close();
        stats.framesDropped++;
    }
    
    pendingFrame = bitmap;
}

function renderLoop() {
    const startTime = performance.now();
    
    if (pendingFrame && !isRendering) {
        isRendering = true;
        
        // Render the frame
        ctx.transferFromImageBitmap(pendingFrame);
        pendingFrame.close();
        pendingFrame = null;
        
        // Update stats
        stats.framesRendered++;
        const renderTime = performance.now() - startTime;
        stats.totalRenderTime += renderTime;
        
        if (renderTime > 16.67) {
            console.warn(\`Slow frame: \${renderTime.toFixed(2)}ms\`);
        }
        
        isRendering = false;
        
        // Notify that frame is rendered
        self.postMessage({ type: 'frameRendered' });
    }
    
    requestAnimationFrame(renderLoop);
}
`;

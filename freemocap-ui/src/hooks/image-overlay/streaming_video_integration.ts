import { OverlayRenderer } from './overlay-topology';
import { createFullEyeTopology } from './eye-tracking-example';
import { PointsDict, Metadata } from './overlay-types';

// ============================================================================
// LAYERED CANVAS APPROACH (RECOMMENDED)
// ============================================================================

export class LayeredVideoOverlay {
  private videoCanvas: HTMLCanvasElement;
  private overlayCanvas: HTMLCanvasElement;
  private videoCtx: CanvasRenderingContext2D;
  private overlayCtx: CanvasRenderingContext2D;
  private renderer: OverlayRenderer;

  constructor(
    videoCanvasId: string,
    overlayCanvasId: string,
    width: number,
    height: number
  ) {
    this.videoCanvas = document.getElementById(videoCanvasId) as HTMLCanvasElement;
    this.overlayCanvas = document.getElementById(overlayCanvasId) as HTMLCanvasElement;
    
    this.videoCanvas.width = width;
    this.videoCanvas.height = height;
    this.overlayCanvas.width = width;
    this.overlayCanvas.height = height;

    this.videoCtx = this.videoCanvas.getContext('2d')!;
    this.overlayCtx = this.overlayCanvas.getContext('2d')!;

    // Create topology
    const topology = createFullEyeTopology({
      width,
      height,
      showCleaned: true,
      showDots: true,
      showEllipse: true
    });

    this.renderer = new OverlayRenderer(topology);
  }

  // Update video frame (less frequently if needed)
  updateVideo(imageData: ImageData): void {
    this.videoCtx.putImageData(imageData, 0, 0);
  }

  // Update overlay (every detection frame)
  updateOverlay(points: PointsDict, metadata: Metadata = {}): void {
    // Clear previous overlay
    this.overlayCtx.clearRect(0, 0, this.overlayCanvas.width, this.overlayCanvas.height);
    
    // Draw new overlay
    this.renderer.render(this.overlayCtx, points, metadata);
  }
}

// ============================================================================
// SINGLE CANVAS APPROACH (SIMPLER)
// ============================================================================

export class SingleCanvasOverlay {
  private canvas: HTMLCanvasElement;
  private ctx: CanvasRenderingContext2D;
  private renderer: OverlayRenderer;

  constructor(canvasId: string, width: number, height: number) {
    this.canvas = document.getElementById(canvasId) as HTMLCanvasElement;
    this.canvas.width = width;
    this.canvas.height = height;
    this.ctx = this.canvas.getContext('2d')!;

    const topology = createFullEyeTopology({
      width,
      height,
      showCleaned: true,
      showDots: true,
      showEllipse: true
    });

    this.renderer = new OverlayRenderer(topology);
  }

  // Update both video and overlay in one call
  updateFrame(imageData: ImageData, points: PointsDict, metadata: Metadata = {}): void {
    // Draw video frame
    this.ctx.putImageData(imageData, 0, 0);
    
    // Draw overlay on top
    this.renderer.render(this.ctx, points, metadata);
  }
}

// ============================================================================
// OFFSCREEN CANVAS IN WORKER (BEST PERFORMANCE)
// ============================================================================

// main.ts
export function setupOffscreenOverlay(canvasId: string, width: number, height: number): void {
  const canvas = document.getElementById(canvasId) as HTMLCanvasElement;
  canvas.width = width;
  canvas.height = height;
  
  const offscreen = canvas.transferControlToOffscreen();
  const worker = new Worker(new URL('./video-worker.ts', import.meta.url));
  
  worker.postMessage({ 
    type: 'init', 
    canvas: offscreen,
    width,
    height
  }, [offscreen]);

  // WebSocket for detections
  const ws = new WebSocket('ws://localhost:8080/detections');
  
  ws.onmessage = (event) => {
    const detections = JSON.parse(event.data);
    worker.postMessage({ 
      type: 'detections', 
      detections 
    });
  };

  // Video stream (from camera or other source)
  setupVideoStream((imageData) => {
    worker.postMessage({ 
      type: 'frame', 
      imageData 
    }, [imageData.data.buffer]);
  });
}

// video-worker.ts
/*
// In your video-worker.ts file:

import { OverlayRenderer } from './overlay-topology';
import { createFullEyeTopology } from './eye-tracking-example';
import { PointsDict, Metadata } from './overlay-types';

let ctx: OffscreenCanvasRenderingContext2D;
let renderer: OverlayRenderer;
let currentFrame: ImageData | null = null;
let currentDetections: PointsDict = {};
let frameCount = 0;

self.onmessage = (e: MessageEvent) => {
  const { type, canvas, width, height, imageData, detections } = e.data;

  if (type === 'init') {
    ctx = canvas.getContext('2d');
    
    const topology = createFullEyeTopology({
      width,
      height,
      showCleaned: true,
      showDots: true,
      showEllipse: true
    });
    
    renderer = new OverlayRenderer(topology);
    render();
  } else if (type === 'frame') {
    currentFrame = imageData;
  } else if (type === 'detections') {
    currentDetections = detections;
  }
};

function render(): void {
  if (ctx && currentFrame) {
    // Draw video frame
    ctx.putImageData(currentFrame, 0, 0);
    
    // Draw overlay
    if (Object.keys(currentDetections).length > 0) {
      renderer.render(ctx, currentDetections, {
        frameIdx: frameCount++,
        totalFrames: 1000,
        viewMode: 'live'
      });
    }
  }
  
  requestAnimationFrame(render);
}
*/

// ============================================================================
// WEBSOCKET DETECTION FORMAT
// ============================================================================

interface DetectionMessage {
  cleaned?: {
    p1?: [number, number];
    p2?: [number, number];
    p3?: [number, number];
    p4?: [number, number];
    p5?: [number, number];
    p6?: [number, number];
    p7?: [number, number];
    p8?: [number, number];
    tear_duct?: [number, number];
    outer_eye?: [number, number];
  };
  raw?: {
    p1?: [number, number];
    p2?: [number, number];
    p3?: [number, number];
    p4?: [number, number];
    p5?: [number, number];
    p6?: [number, number];
    p7?: [number, number];
    p8?: [number, number];
    tear_duct?: [number, number];
    outer_eye?: [number, number];
  };
}

// Example Python server that sends detections:
/*
import json
import asyncio
import websockets

async def send_detections(websocket, path):
    while True:
        detections = {
            'cleaned': {
                'p1': [100.5, 200.3],
                'p2': [110.2, 195.8],
                # ... other points
                'tear_duct': [80.0, 210.0],
                'outer_eye': [150.0, 205.0]
            }
        }
        
        await websocket.send(json.dumps(detections))
        await asyncio.sleep(0.033)  # ~30 FPS

start_server = websockets.serve(send_detections, "localhost", 8080)
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
*/

// ============================================================================
// HELPER FUNCTION
// ============================================================================

function setupVideoStream(callback: (imageData: ImageData) => void): void {
  // Example: Get video from camera
  navigator.mediaDevices.getUserMedia({ video: true })
    .then(stream => {
      const video = document.createElement('video');
      video.srcObject = stream;
      video.play();

      const tempCanvas = document.createElement('canvas');
      const tempCtx = tempCanvas.getContext('2d')!;

      function captureFrame(): void {
        if (video.readyState === video.HAVE_ENOUGH_DATA) {
          tempCanvas.width = video.videoWidth;
          tempCanvas.height = video.videoHeight;
          tempCtx.drawImage(video, 0, 0);
          const imageData = tempCtx.getImageData(0, 0, tempCanvas.width, tempCanvas.height);
          callback(imageData);
        }
        requestAnimationFrame(captureFrame);
      }

      captureFrame();
    });
}

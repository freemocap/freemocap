// frame-processor.ts
import { parseMultiFramePayload, ParsedFrame } from "@/services/server/server-helpers/frame-processor/binary-frame-parser";

export interface FrameData {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    bitmap: ImageBitmap;
}

export interface ProcessedFrameResult {
    frames: FrameData[];
    cameraIds: Set<string>;
    frameNumbers: Set<number>;
}

export class FrameProcessor {
    private lastFrameTime: Map<string, number> = new Map();
    private currentFps: Map<string, number> = new Map();

    public async processFramePayload(data: ArrayBuffer): Promise<ProcessedFrameResult | null> {
        try {
            const parsedFrames = await parseMultiFramePayload(data);
            if (!parsedFrames) {
                console.warn('Failed to parse frame payload');
                return null;
            }

            const cameraIds = new Set<string>();
            const frameNumbers = new Set<number>();

            // Convert ParsedFrame to FrameData (they have the same structure now)
            const frames: FrameData[] = parsedFrames.map((frame: ParsedFrame) => ({
                cameraId: frame.cameraId,
                cameraIndex: frame.cameraIndex,
                frameNumber: frame.frameNumber,
                width: frame.width,
                height: frame.height,
                colorChannels: frame.colorChannels,
                bitmap: frame.bitmap
            }));

            for (const frame of frames) {
                cameraIds.add(frame.cameraId);
                frameNumbers.add(frame.frameNumber);

                // Track frame timing and calculate FPS
                const now = performance.now();
                const lastTime = this.lastFrameTime.get(frame.cameraId);
                if (lastTime) {
                    const fps = 1000 / (now - lastTime);
                    this.currentFps.set(frame.cameraId, fps);
                }
                this.lastFrameTime.set(frame.cameraId, now);
            }

            return { frames, cameraIds, frameNumbers };
        } catch (error) {
            console.error('Error processing frame payload:', error);
            throw new Error(`Frame processing failed: ${error}`);
        }
    }

    public getFps(cameraId: string): number | null {
        return this.currentFps.get(cameraId) ?? null;
    }

    public reset(): void {
        this.lastFrameTime.clear();
        this.currentFps.clear();
    }
}

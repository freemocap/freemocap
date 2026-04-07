// base-overlay-renderer.ts
import { z } from 'zod';

// Generic types for any observation
export interface Point2D {
    x: number;
    y: number;
    id?: string | number;
    visibility?: number;  // 0-1, for confidence/visibility
}

export interface Segment {
    proximal: string | number;
    distal: string | number;
}

export interface ModelInfo {
    name: string;
    tracker_name: string;
    aspects: Record<string, AspectInfo>;
    order: string[];
}

export interface AspectInfo {
    tracked_points: {
        type: 'list' | 'generated';
        names?: string[];
        convention?: string;
        count?: number;
    };
    segment_connections?: Record<string, Segment>;
    joint_hierarchy?: Record<string, string[]>;
}

export interface DrawStyle {
    pointColor: string;
    pointStroke: string;
    pointRadius: number;
    lineColor: string;
    lineWidth: number;
    labelColor: string;
    labelStroke: string;
    labelFontSize: number;
    showLabels: boolean;
}

export interface ObservationMetadata {
    frame_number: number;
    [key: string]: any;  // Allow additional metadata
}

export abstract class BaseOverlayRenderer {
    protected offscreenCanvas: OffscreenCanvas;
    protected ctx: OffscreenCanvasRenderingContext2D;
    protected modelInfo: ModelInfo | null = null;
    
    // Common style constants
    protected readonly INFO_BG = 'rgba(0, 0, 0, 0.7)';
    protected readonly TEXT_COLOR = '#ccc';
    protected readonly TEXT_STROKE = '#111';
    
    constructor() {
        this.offscreenCanvas = new OffscreenCanvas(1, 1);
        const ctx = this.offscreenCanvas.getContext('2d', {
            alpha: true,
            desynchronized: true,
        });

        if (!ctx) {
            throw new Error('Failed to get 2D context for overlay renderer');
        }

        this.ctx = ctx;
    }

    /**
     * Set the model info for this renderer
     */
    public setModelInfo(modelInfo: ModelInfo): void {
        this.modelInfo = modelInfo;
    }

    /**
     * Main composite method - to be implemented by specific renderers
     */
    public abstract compositeFrame(
        sourceBitmap: ImageBitmap,
        observation: any | null,
    ): Promise<ImageBitmap>;

    /**
     * Resize canvas if needed and draw source image
     */
    protected prepareCanvas(sourceBitmap: ImageBitmap): void {
        const { width, height } = sourceBitmap;

        if (this.offscreenCanvas.width !== width || this.offscreenCanvas.height !== height) {
            this.offscreenCanvas.width = width;
            this.offscreenCanvas.height = height;
        }

        this.ctx.clearRect(0, 0, width, height);
        this.ctx.drawImage(sourceBitmap, 0, 0);
    }

    /**
     * Generic method to draw points
     */
    protected drawPoints(
        points: Point2D[],
        style: DrawStyle
    ): void {
        for (const point of points) {
            // Skip invalid points
            if (!this.isValidPoint(point)) continue;

            // Optional visibility threshold
            if (point.visibility !== undefined && point.visibility < 0.5) continue;

            // Draw filled circle
            this.ctx.fillStyle = style.pointColor;
            this.ctx.beginPath();
            this.ctx.arc(point.x, point.y, style.pointRadius, 0, Math.PI * 2);
            this.ctx.fill();

            // Draw stroke
            this.ctx.strokeStyle = style.pointStroke;
            this.ctx.lineWidth = 2;
            this.ctx.stroke();

            // Draw label if enabled
            if (style.showLabels && point.id !== undefined) {
                this.drawText(
                    point.id.toString(),
                    point.x + style.pointRadius + 3,
                    point.y - style.pointRadius - 3,
                    style.labelFontSize,
                    style.labelColor,
                    style.labelStroke,
                    2
                );
            }
        }
    }

    /**
     * Generic method to draw segments/connections between points
     */
    protected drawSegments(
        points: Map<string | number, Point2D>,
        segments: Record<string, Segment>,
        style: DrawStyle
    ): void {
        for (const [_, segment] of Object.entries(segments)) {
            const proximalPoint = points.get(segment.proximal);
            const distalPoint = points.get(segment.distal);

            if (!proximalPoint || !distalPoint) continue;
            if (!this.isValidPoint(proximalPoint) || !this.isValidPoint(distalPoint)) continue;

            // Draw line
            this.ctx.strokeStyle = style.lineColor;
            this.ctx.lineWidth = style.lineWidth;
            this.ctx.beginPath();
            this.ctx.moveTo(proximalPoint.x, proximalPoint.y);
            this.ctx.lineTo(distalPoint.x, distalPoint.y);
            this.ctx.stroke();
        }
    }

    /**
     * Generic method to draw a polygon (like ArUco markers)
     */
    protected drawPolygon(
        corners: [number, number][],
        style: DrawStyle,
        fillPoints: boolean = true,
        label?: string
    ): void {
        if (corners.length < 3) return;

        // Draw outline
        this.ctx.strokeStyle = style.lineColor;
        this.ctx.lineWidth = style.lineWidth;
        this.ctx.beginPath();
        this.ctx.moveTo(corners[0][0], corners[0][1]);
        for (let i = 1; i < corners.length; i++) {
            this.ctx.lineTo(corners[i][0], corners[i][1]);
        }
        this.ctx.closePath();
        this.ctx.stroke();

        // Draw corner points if requested
        if (fillPoints) {
            this.ctx.fillStyle = style.pointColor;
            for (const corner of corners) {
                this.ctx.beginPath();
                this.ctx.arc(corner[0], corner[1], style.pointRadius, 0, Math.PI * 2);
                this.ctx.fill();
            }
        }

        // Draw label at center if provided
        if (label) {
            const centerX = corners.reduce((sum, c) => sum + c[0], 0) / corners.length;
            const centerY = corners.reduce((sum, c) => sum + c[1], 0) / corners.length;

            this.drawText(
                label,
                centerX,
                centerY,
                style.labelFontSize * 1.2,
                this.TEXT_COLOR,
                style.pointColor,
                3,
                'bold'
            );
        }
    }

    /**
     * Draw text with stroke (outline)
     */
    protected drawText(
        text: string,
        x: number,
        y: number,
        fontSize: number,
        fillColor: string,
        strokeColor: string,
        strokeWidth: number,
        fontWeight: string = 'normal'
    ): void {
        this.ctx.font = `${fontWeight} ${fontSize}px Arial, sans-serif`;
        this.ctx.textBaseline = 'middle';

        // Draw stroke (outline)
        this.ctx.strokeStyle = strokeColor;
        this.ctx.lineWidth = strokeWidth + 2;
        this.ctx.strokeText(text, x, y);

        // Draw fill
        this.ctx.fillStyle = fillColor;
        this.ctx.fillText(text, x, y);
    }

    /**
     * Draw info overlay with metadata
     */
    protected drawInfoOverlay(
        metadata: ObservationMetadata,
        additionalInfo?: string[]
    ): void {
        const lines: string[] = [
            `Frame: ${metadata.frame_number}`,
            ...(additionalInfo || [])
        ];

        // Calculate background size
        const lineHeight = 25;
        const bgHeight = lines.length * lineHeight + 10;
        const bgWidth = 500;

        // Draw background
        this.ctx.fillStyle = this.INFO_BG;
        this.ctx.fillRect(5, 5, bgWidth, bgHeight);

        // Draw lines
        let y = 25;
        for (const line of lines) {
            this.drawText(line, 10, y, 14, this.TEXT_COLOR, this.TEXT_STROKE, 2);
            y += lineHeight;
        }
    }

    /**
     * Check if a point is valid (not NaN or undefined)
     */
    protected isValidPoint(point: Point2D): boolean {
        return (
            point &&
            typeof point.x === 'number' &&
            typeof point.y === 'number' &&
            !isNaN(point.x) &&
            !isNaN(point.y) &&
            isFinite(point.x) &&
            isFinite(point.y)
        );
    }

    /**
     * Create final bitmap from canvas
     */
    protected async createBitmap(sourceBitmap: ImageBitmap): Promise<ImageBitmap> {
        const compositeBitmap = await createImageBitmap(this.offscreenCanvas);
        sourceBitmap.close();
        return compositeBitmap;
    }

    public destroy(): void {
        // Cleanup if needed
    }
}
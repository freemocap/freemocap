import {ArucoMarker, CharucoObservation, CharucoPoint} from "@/services/server/server-helpers/charuco_types";

/**
 * Composites overlay graphics directly onto an ImageBitmap.
 * Returns a new ImageBitmap with the overlay drawn on top.
 */
export class FrameCompositor {
    private offscreenCanvas: OffscreenCanvas;
    private ctx: OffscreenCanvasRenderingContext2D;

    // Style constants
    private readonly CHARUCO_COLOR = '#00FF00';
    private readonly CHARUCO_STROKE = '#009600';
    private readonly ARUCO_COLOR = '#FF6400';
    private readonly ARUCO_STROKE = '#C85000';
    private readonly TEXT_COLOR = '#ccc';
    private readonly TEXT_STROKE = '#111';
    private readonly INFO_BG = 'rgba(0, 0, 0, 0.7)';
    private readonly SCALE: number = 1.0;

    constructor() {
        // Create a reusable offscreen canvas for compositing
        this.offscreenCanvas = new OffscreenCanvas(1, 1);
        const ctx = this.offscreenCanvas.getContext('2d', {
            alpha: true,
            desynchronized: true,
        });

        if (!ctx) {
            throw new Error('Failed to get 2D context for compositor');
        }

        this.ctx = ctx;
    }

    /**
     * Composite overlay onto an ImageBitmap and return a new ImageBitmap
     */
    public async compositeFrame(
        sourceBitmap: ImageBitmap,
        observation: CharucoObservation | null,
    ): Promise<ImageBitmap> {
        const { width, height } = sourceBitmap;

        // Resize canvas if needed
        if (this.offscreenCanvas.width !== width || this.offscreenCanvas.height !== height) {
            this.offscreenCanvas.width = width;
            this.offscreenCanvas.height = height;
        }

        // Draw source image
        this.ctx.clearRect(0, 0, width, height);
        this.ctx.drawImage(sourceBitmap, 0, 0);

        // Draw overlay if we have observation data
        if (observation) {
            this.drawOverlay(observation);
        }

        // Create new bitmap from composited result
        const compositeBitmap = await createImageBitmap(this.offscreenCanvas);

        // Close the source bitmap since we're done with it
        sourceBitmap.close();

        return compositeBitmap;
    }

    private drawOverlay(observation: CharucoObservation): void {
        this.ctx.save();
        this.ctx.scale(this.SCALE, this.SCALE);

        // Draw ArUco markers (behind Charuco corners)
        this.drawArucoMarkers(observation.aruco_markers);

        // Draw Charuco corners
        this.drawCharucoCorners(observation.charuco_corners);

        // Draw info overlay
        this.drawInfoOverlay(observation);

        this.ctx.restore();
    }

    private drawCharucoCorners(corners: CharucoPoint[]): void {
        if (corners.length === 0) return;

        for (const corner of corners) {
            // Draw filled circle
            this.ctx.fillStyle = this.CHARUCO_COLOR;
            this.ctx.beginPath();
            this.ctx.arc(corner.x, corner.y, 5, 0, Math.PI * 2);
            this.ctx.fill();

            // Draw stroke
            this.ctx.strokeStyle = this.CHARUCO_STROKE;
            this.ctx.lineWidth = 2;
            this.ctx.stroke();

            // Draw ID label
            this.drawText(
                corner.id.toString(),
                corner.x + 8,
                corner.y - 8,
                10,
                this.CHARUCO_COLOR,
                this.TEXT_STROKE,
                2
            );
        }
    }

    private drawArucoMarkers(markers: ArucoMarker[]): void {
        if (markers.length === 0) return;

        for (const marker of markers) {
            // Draw marker outline
            this.ctx.strokeStyle = this.ARUCO_COLOR;
            this.ctx.lineWidth = 3;
            this.ctx.beginPath();

            // Draw square connecting the 4 corners
            this.ctx.moveTo(marker.corners[0][0], marker.corners[0][1]);
            for (let i = 1; i < 4; i++) {
                this.ctx.lineTo(marker.corners[i][0], marker.corners[i][1]);
            }
            this.ctx.closePath();
            this.ctx.stroke();

            // Draw corner points
            this.ctx.fillStyle = this.ARUCO_COLOR;
            for (const corner of marker.corners) {
                this.ctx.beginPath();
                this.ctx.arc(corner[0], corner[1], 4, 0, Math.PI * 2);
                this.ctx.fill();
            }

            // Draw marker ID at center
            const centerX = marker.corners.reduce((sum, c) => sum + c[0], 0) / marker.corners.length;
            const centerY = marker.corners.reduce((sum, c) => sum + c[1], 0) / marker.corners.length;

            this.drawText(
                marker.id.toString(),
                centerX,
                centerY,
                14,
                this.TEXT_COLOR,
                this.ARUCO_COLOR,
                3,
                'bold'
            );
        }
    }

    private drawInfoOverlay(observation: CharucoObservation): void {
        const { metadata, frame_number } = observation;

        // Info text
        const infoText =
            `Frame: ${frame_number} | ` +
            `Charuco: ${metadata.n_charuco_detected}/${metadata.n_charuco_total} | ` +
            `ArUco: ${metadata.n_aruco_detected}/${metadata.n_aruco_total}` +
            (metadata.has_pose ? ' | POSE ✓' : '');

        // Status text
        let statusText = '';
        let statusColor = '';
        if (metadata.n_charuco_detected === 0 && metadata.n_aruco_detected === 0) {
            statusText = '⚠ NO BOARD DETECTED';
            statusColor = '#FF4444';
        } else if (metadata.n_charuco_detected < 4) {
            statusText = '⚠ INSUFFICIENT CORNERS';
            statusColor = '#FFAA00';
        } else {
            statusText = '✓ BOARD DETECTED';
            statusColor = '#00FF00';
        }

        // Draw info background
        this.ctx.fillStyle = this.INFO_BG;
        this.ctx.fillRect(5, 5, 500, 60);

        // Draw info text
        this.drawText(infoText, 10, 25, 14, this.TEXT_COLOR, this.TEXT_STROKE, 2);

        // Draw status text
        this.drawText(statusText, 10, 50, 16, statusColor, this.TEXT_STROKE, 2);
    }

    private drawText(
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

    public destroy(): void {
        // Cleanup if needed
    }
}

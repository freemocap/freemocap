import { CharucoObservation, CharucoPoint, ArucoMarker } from './charuco-observation-types';

interface RenderStats {
    lastRenderTime: number;
    frameCount: number;
    avgRenderTime: number;
}

export class CharucoOverlayRenderer {
    private canvas: HTMLCanvasElement;
    private ctx: CanvasRenderingContext2D;
    private latestObservation: CharucoObservation | null = null;
    private animationFrameId: number | null = null;
    private stats: RenderStats = {
        lastRenderTime: 0,
        frameCount: 0,
        avgRenderTime: 0,
    };

    // Style constants (cache for performance)
    private readonly CHARUCO_COLOR = '#00FF00'; // Green
    private readonly CHARUCO_STROKE = '#009600';
    private readonly ARUCO_COLOR = '#FF6400'; // Orange
    private readonly ARUCO_STROKE = '#C85000';
    private readonly TEXT_COLOR = '#FFFFFF';
    private readonly TEXT_STROKE = '#000000';
    private readonly INFO_BG = 'rgba(0, 0, 0, 0.7)';

    constructor(canvas: HTMLCanvasElement) {
        const ctx = canvas.getContext('2d', {
            alpha: true,
            desynchronized: true, // Performance hint for faster rendering
        });

        if (!ctx) {
            throw new Error('Failed to get 2D context for overlay canvas');
        }

        this.canvas = canvas;
        this.ctx = ctx;

        // Start render loop
        this.startRenderLoop();
    }

    public updateObservation(observation: CharucoObservation): void {
        this.latestObservation = observation;
        // No need to manually trigger render - the loop handles it
    }

    private startRenderLoop(): void {
        const render = (): void => {
            if (this.latestObservation) {
                const startTime = performance.now();
                this.renderOverlay(this.latestObservation);
                const renderTime = performance.now() - startTime;

                // Update stats
                this.stats.frameCount++;
                this.stats.lastRenderTime = renderTime;
                this.stats.avgRenderTime =
                    (this.stats.avgRenderTime * (this.stats.frameCount - 1) + renderTime) /
                    this.stats.frameCount;

                // Warn if slow
                if (renderTime > 16.67) {
                    console.warn(`Slow overlay render: ${renderTime.toFixed(2)}ms`);
                }
            }

            this.animationFrameId = requestAnimationFrame(render);
        };

        this.animationFrameId = requestAnimationFrame(render);
    }

    private renderOverlay(observation: CharucoObservation): void {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Set canvas size if changed (e.g., rotation)
        if (
            this.canvas.width !== observation.metadata.image_width ||
            this.canvas.height !== observation.metadata.image_height
        ) {
            this.canvas.width = observation.metadata.image_width;
            this.canvas.height = observation.metadata.image_height;
        }

        // Draw ArUco markers (behind Charuco corners)
        this.drawArucoMarkers(observation.aruco_markers);

        // Draw Charuco corners
        this.drawCharucoCorners(observation.charuco_corners);

        // Draw info overlay
        this.drawInfoOverlay(observation);
    }

    private drawCharucoCorners(corners: CharucoPoint[]): void {
        if (corners.length === 0) return;

        this.ctx.save();

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

        this.ctx.restore();
    }

    private drawArucoMarkers(markers: ArucoMarker[]): void {
        if (markers.length === 0) return;

        this.ctx.save();

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
            const centerX =
                marker.corners.reduce((sum, c) => sum + c[0], 0) / marker.corners.length;
            const centerY =
                marker.corners.reduce((sum, c) => sum + c[1], 0) / marker.corners.length;

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

        this.ctx.restore();
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
        this.drawText(infoText, 10, 25, 16, this.TEXT_COLOR, this.TEXT_STROKE, 2);

        // Draw status text
        this.drawText(statusText, 10, 50, 14, statusColor, this.TEXT_STROKE, 2);
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
        if (this.animationFrameId !== null) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
        this.latestObservation = null;
    }

    public getStats(): RenderStats {
        return { ...this.stats };
    }
}

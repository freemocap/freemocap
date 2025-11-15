// charuco-overlay-renderer.ts

import {
    BaseOverlayRenderer,
    DrawStyle,
    Point2D
} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import {
    ArucoMarker,
    CharucoObservation,
    CharucoPoint
} from "@/services/server/server-helpers/image-overlay/charuco-types";

export class CharucoOverlayRenderer extends BaseOverlayRenderer {
    // Charuco-specific styles
    private readonly charucoStyle: DrawStyle = {
        pointColor: '#00FF00',
        pointStroke: '#009600',
        pointRadius: 5,
        lineColor: '#00FF00',
        lineWidth: 2,
        labelColor: '#00FF00',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 10,
        showLabels: true,
    };

    private readonly arucoStyle: DrawStyle = {
        pointColor: '#FF6400',
        pointStroke: '#C85000',
        pointRadius: 4,
        lineColor: '#FF6400',
        lineWidth: 3,
        labelColor: this.TEXT_COLOR,
        labelStroke: '#FF6400',
        labelFontSize: 14,
        showLabels: true,
    };

    /**
     * Composite charuco overlay onto frame
     */
    public async compositeFrame(
        sourceBitmap: ImageBitmap,
        observation: CharucoObservation | null,
    ): Promise<ImageBitmap> {
        this.prepareCanvas(sourceBitmap);

        if (observation) {
            this.drawCharucoOverlay(observation);
        }

        return this.createBitmap(sourceBitmap);
    }

    private drawCharucoOverlay(observation: CharucoObservation): void {
        this.ctx.save();

        // Draw ArUco markers first (behind Charuco corners)
        this.drawArucoMarkers(observation.aruco_markers);

        // Draw Charuco corners
        this.drawCharucoCorners(observation.charuco_corners);

        // Draw segments if model info is available
        if (this.modelInfo) {
            this.drawCharucoSegments(observation.charuco_corners);
        }

        // Draw info overlay
        this.drawCharucoInfo(observation);

        this.ctx.restore();
    }

    private drawCharucoCorners(corners: CharucoPoint[]): void {
        if (corners.length === 0) return;

        // Convert CharucoPoint[] to Point2D[]
        const points: Point2D[] = corners.map(corner => ({
            x: corner.x,
            y: corner.y,
            id: corner.id,
        }));

        this.drawPoints(points, this.charucoStyle);
    }

    private drawCharucoSegments(corners: CharucoPoint[]): void {
        if (!this.modelInfo || corners.length === 0) return;

        // Create a map of corner ID to Point2D
        const pointMap = new Map<string | number, Point2D>();
        for (const corner of corners) {
            pointMap.set(corner.id.toString(), {
                x: corner.x,
                y: corner.y,
                id: corner.id,
            });
        }

        // Get segments from model info
        const bodyAspect = this.modelInfo.aspects['body'];
        if (bodyAspect?.segment_connections) {
            this.drawSegments(pointMap, bodyAspect.segment_connections, {
                ...this.charucoStyle,
                lineColor: 'rgba(0, 255, 0, 0.5)',  // Semi-transparent green
                lineWidth: 1,
            });
        }
    }

    private drawArucoMarkers(markers: ArucoMarker[]): void {
        if (markers.length === 0) return;

        for (const marker of markers) {
            this.drawPolygon(
                marker.corners,
                this.arucoStyle,
                true,
                marker.id.toString()
            );
        }
    }

    private drawCharucoInfo(observation: CharucoObservation): void {
        const { metadata, frame_number } = observation;

        // Build status info
        let statusText = '';
        let statusColor = '';
        if (metadata.n_charuco_detected === 0 && metadata.n_aruco_detected === 0) {
            statusText = '⚠ NO BOARD DETECTED';
            statusColor = '#FF4444';
        } else if (metadata.n_charuco_detected < 4) {
            statusText = '⚠ INSUFFICIENT CORNERS';
            statusColor = '#FFAA00';
        } else {
            statusText = '✔ BOARD DETECTED';
            statusColor = '#00FF00';
        }

        const additionalInfo = [
            `Charuco: ${metadata.n_charuco_detected}/${metadata.n_charuco_total} | ` +
            `ArUco: ${metadata.n_aruco_detected}/${metadata.n_aruco_total}` +
            (metadata.has_pose ? ' | POSE ✔' : ''),
            statusText,
        ];

        // Draw background and info
        this.ctx.fillStyle = this.INFO_BG;
        this.ctx.fillRect(5, 5, 500, 85);

        this.drawText(
            `Frame: ${frame_number}`,
            10,
            25,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2
        );

        this.drawText(
            additionalInfo[0],
            10,
            50,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2
        );

        this.drawText(
            additionalInfo[1],
            10,
            75,
            16,
            statusColor,
            this.TEXT_STROKE,
            2
        );
    }
}

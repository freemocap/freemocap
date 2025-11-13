// mediapipe-overlay-renderer.ts

import {
    BaseOverlayRenderer,
    DrawStyle,
    Point2D
} from "@/services/server/server-helpers/image-overlay/image-overlay-system";

export interface MediapipePoint {
    name: string;
    x: number;
    y: number;
    z?: number;
    visibility?: number;
}

export interface MediapipeObservation {
    message_type: 'mediapipe_overlay';
    camera_id: string;
    frame_number: number;
    body_points?: MediapipePoint[];
    right_hand_points?: MediapipePoint[];
    left_hand_points?: MediapipePoint[];
    face_points?: MediapipePoint[];
    metadata: {
        image_width: number;
        image_height: number;
        n_body_detected: number;
        n_right_hand_detected: number;
        n_left_hand_detected: number;
        n_face_detected: number;
    };
}

export class MediapipeOverlayRenderer extends BaseOverlayRenderer {
    // Aspect-specific styles
    private readonly bodyStyle: DrawStyle = {
        pointColor: '#00FF00',
        pointStroke: '#008800',
        pointRadius: 4,
        lineColor: '#00FF00',
        lineWidth: 2,
        labelColor: '#00FF00',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,  // Too many points to label
    };

    private readonly rightHandStyle: DrawStyle = {
        pointColor: '#FF6400',
        pointStroke: '#AA4400',
        pointRadius: 3,
        lineColor: '#FF6400',
        lineWidth: 1.5,
        labelColor: '#FF6400',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly leftHandStyle: DrawStyle = {
        pointColor: '#00AAFF',
        pointStroke: '#0066AA',
        pointRadius: 3,
        lineColor: '#00AAFF',
        lineWidth: 1.5,
        labelColor: '#00AAFF',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly faceStyle: DrawStyle = {
        pointColor: '#FFD700',
        pointStroke: '#AA9900',
        pointRadius: 1,
        lineColor: '#FFD700',
        lineWidth: 1,
        labelColor: '#FFD700',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 6,
        showLabels: false,
    };

    /**
     * Composite mediapipe overlay onto frame
     */
    public async compositeFrame(
        sourceBitmap: ImageBitmap,
        observation: MediapipeObservation | null,
    ): Promise<ImageBitmap> {
        this.prepareCanvas(sourceBitmap);

        if (observation) {
            this.drawMediapipeOverlay(observation);
        }

        return this.createBitmap(sourceBitmap);
    }

    private drawMediapipeOverlay(observation: MediapipeObservation): void {
        this.ctx.save();

        // Draw each aspect in order (face behind, body in middle, hands on top)
        if (observation.face_points) {
            this.drawFaceAspect(observation.face_points);
        }

        if (observation.body_points) {
            this.drawBodyAspect(observation.body_points);
        }

        if (observation.right_hand_points) {
            this.drawHandAspect(observation.right_hand_points, 'right_hand', this.rightHandStyle);
        }

        if (observation.left_hand_points) {
            this.drawHandAspect(observation.left_hand_points, 'left_hand', this.leftHandStyle);
        }

        // Draw info overlay
        this.drawMediapipeInfo(observation);

        this.ctx.restore();
    }

    private drawBodyAspect(points: MediapipePoint[]): void {
        if (points.length === 0) return;

        // Create point map for segment drawing
        const pointMap = new Map<string | number, Point2D>();
        const point2DArray: Point2D[] = [];

        for (const point of points) {
            const point2D: Point2D = {
                x: point.x,
                y: point.y,
                id: point.name,
                visibility: point.visibility,
            };
            pointMap.set(point.name, point2D);
            point2DArray.push(point2D);
        }

        // Draw segments first (behind points)
        if (this.modelInfo?.aspects['body']?.segment_connections) {
            this.drawSegments(pointMap, this.modelInfo.aspects['body'].segment_connections, {
                ...this.bodyStyle,
                lineColor: 'rgba(0, 255, 0, 0.6)',  // Semi-transparent
            });
        }

        // Draw points on top
        this.drawPoints(point2DArray, this.bodyStyle);

        // Highlight key points with labels
        this.drawKeyBodyPoints(pointMap);
    }

    private drawKeyBodyPoints(pointMap: Map<string | number, Point2D>): void {
        // Label only important landmarks for clarity
        const keyPoints = ['nose', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip'];

        for (const key of keyPoints) {
            const point = pointMap.get(key);
            if (point && this.isValidPoint(point)) {
                this.drawText(
                    key.replace('_', ' '),
                    point.x + 5,
                    point.y - 5,
                    8,
                    this.bodyStyle.labelColor,
                    this.bodyStyle.labelStroke,
                    1
                );
            }
        }
    }

    private drawHandAspect(
        points: MediapipePoint[],
        aspectName: string,
        style: DrawStyle
    ): void {
        if (points.length === 0) return;

        const pointMap = new Map<string | number, Point2D>();
        const point2DArray: Point2D[] = [];

        for (const point of points) {
            const point2D: Point2D = {
                x: point.x,
                y: point.y,
                id: point.name,
                visibility: point.visibility,
            };
            pointMap.set(point.name, point2D);
            point2DArray.push(point2D);
        }

        // Draw hand skeleton connections
        this.drawHandConnections(pointMap, style);

        // Draw points
        this.drawPoints(point2DArray, style);
    }

    private drawHandConnections(
        pointMap: Map<string | number, Point2D>,
        style: DrawStyle
    ): void {
        // Define hand connections (MediaPipe hand landmark connections)
        const handConnections = [
            // Thumb
            ['wrist', 'thumb_cmc'],
            ['thumb_cmc', 'thumb_mcp'],
            ['thumb_mcp', 'thumb_ip'],
            ['thumb_ip', 'thumb_tip'],
            // Index finger
            ['wrist', 'index_finger_mcp'],
            ['index_finger_mcp', 'index_finger_pip'],
            ['index_finger_pip', 'index_finger_dip'],
            ['index_finger_dip', 'index_finger_tip'],
            // Middle finger
            ['wrist', 'middle_finger_mcp'],
            ['middle_finger_mcp', 'middle_finger_pip'],
            ['middle_finger_pip', 'middle_finger_dip'],
            ['middle_finger_dip', 'middle_finger_tip'],
            // Ring finger
            ['wrist', 'ring_finger_mcp'],
            ['ring_finger_mcp', 'ring_finger_pip'],
            ['ring_finger_pip', 'ring_finger_dip'],
            ['ring_finger_dip', 'ring_finger_tip'],
            // Pinky
            ['wrist', 'pinky_mcp'],
            ['pinky_mcp', 'pinky_pip'],
            ['pinky_pip', 'pinky_dip'],
            ['pinky_dip', 'pinky_tip'],
            // Palm connections
            ['index_finger_mcp', 'middle_finger_mcp'],
            ['middle_finger_mcp', 'ring_finger_mcp'],
            ['ring_finger_mcp', 'pinky_mcp'],
        ];

        for (const [start, end] of handConnections) {
            const startPoint = pointMap.get(start);
            const endPoint = pointMap.get(end);

            if (startPoint && endPoint && this.isValidPoint(startPoint) && this.isValidPoint(endPoint)) {
                this.ctx.strokeStyle = style.lineColor;
                this.ctx.lineWidth = style.lineWidth;
                this.ctx.beginPath();
                this.ctx.moveTo(startPoint.x, startPoint.y);
                this.ctx.lineTo(endPoint.x, endPoint.y);
                this.ctx.stroke();
            }
        }
    }

    private drawFaceAspect(points: MediapipePoint[]): void {
        if (points.length === 0) return;

        // For face, we just draw the points as a mesh without connections
        // (too many points to draw connections clearly)
        const point2DArray: Point2D[] = points.map(point => ({
            x: point.x,
            y: point.y,
            id: point.name,
            visibility: point.visibility,
        }));

        this.drawPoints(point2DArray, this.faceStyle);

        // Optionally draw face contour lines if we have the indices
        if (this.modelInfo?.aspects['face']) {
            this.drawFaceContour(points);
        }
    }

    private drawFaceContour(points: MediapipePoint[]): void {
        // Draw simplified face contour for better visibility
        // This would use the face contour indices from the model info
        // For now, just highlight key face points
        const keyFacePoints = points.filter(p =>
            p.name.includes('eye') ||
            p.name.includes('mouth') ||
            p.name.includes('nose')
        );

        const highlightStyle = {
            ...this.faceStyle,
            pointRadius: 2,
            pointColor: '#FFFF00',
        };

        this.drawPoints(
            keyFacePoints.map(p => ({
                x: p.x,
                y: p.y,
                id: p.name,
                visibility: p.visibility,
            })),
            highlightStyle
        );
    }

    private drawMediapipeInfo(observation: MediapipeObservation): void {
        const { metadata, frame_number } = observation;

        // Build detection status
        const detections: string[] = [];
        if (metadata.n_body_detected > 0) detections.push('Body');
        if (metadata.n_right_hand_detected > 0) detections.push('R-Hand');
        if (metadata.n_left_hand_detected > 0) detections.push('L-Hand');
        if (metadata.n_face_detected > 0) detections.push('Face');

        const statusText = detections.length > 0
            ? `✔ Detected: ${detections.join(', ')}`
            : '⚠ No detection';

        const statusColor = detections.length > 0 ? '#00FF00' : '#FF4444';

        // Draw info background
        this.ctx.fillStyle = this.INFO_BG;
        this.ctx.fillRect(5, 5, 500, 85);

        // Draw frame info
        this.drawText(
            `Frame: ${frame_number}`,
            10,
            25,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2
        );

        // Draw detection counts
        this.drawText(
            `Body: ${metadata.n_body_detected} | Hands: ${metadata.n_right_hand_detected + metadata.n_left_hand_detected} | Face: ${metadata.n_face_detected > 0 ? '✔' : '✗'}`,
            10,
            50,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2
        );

        // Draw status
        this.drawText(
            statusText,
            10,
            75,
            16,
            statusColor,
            this.TEXT_STROKE,
            2
        );
    }
}

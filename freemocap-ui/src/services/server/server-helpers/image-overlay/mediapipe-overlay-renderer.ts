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
    // Body styles split by side
    private readonly bodyStyleCenter: DrawStyle = {
        pointColor: '#00AA00',
        pointStroke: '#008800',
        pointRadius: 4,
        lineColor: 'rgba(20, 255, 20, 0.6)',
        lineWidth: 2,
        labelColor: '#00AA00',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly bodyStyleRight: DrawStyle = {
        pointColor: '#FF4444',
        pointStroke: '#AA0000',
        pointRadius: 4,
        lineColor: 'rgba(255, 68, 68, 0.6)',
        lineWidth: 2,
        labelColor: '#FF4444',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly bodyStyleLeft: DrawStyle = {
        pointColor: '#4488FF',
        pointStroke: '#0044AA',
        pointRadius: 4,
        lineColor: 'rgba(68, 136, 255, 0.6)',
        lineWidth: 2,
        labelColor: '#4488FF',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
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

    private getBodySide(name: string): 'left' | 'right' | 'center' {
        if (name.includes('left')) return 'left';
        if (name.includes('right')) return 'right';
        return 'center';
    }

    private getBodyStyleForSide(side: 'left' | 'right' | 'center'): DrawStyle {
        switch (side) {
            case 'left': return this.bodyStyleLeft;
            case 'right': return this.bodyStyleRight;
            case 'center': return this.bodyStyleCenter;
        }
    }

    private drawBodyAspect(points: MediapipePoint[]): void {
        if (points.length === 0) return;

        // Create point map for segment drawing
        const pointMap = new Map<string | number, Point2D>();
        const leftPoints: Point2D[] = [];
        const rightPoints: Point2D[] = [];
        const centerPoints: Point2D[] = [];

        for (const point of points) {
            const point2D: Point2D = {
                x: point.x,
                y: point.y,
                id: point.name,
                visibility: point.visibility,
            };
            pointMap.set(point.name, point2D);

            const side = this.getBodySide(point.name);
            if (side === 'left') leftPoints.push(point2D);
            else if (side === 'right') rightPoints.push(point2D);
            else centerPoints.push(point2D);
        }

        // Draw body skeleton connections (behind points)
        this.drawBodyConnections(pointMap);

        // Draw points on top, color-coded by side
        this.drawPoints(leftPoints, this.bodyStyleLeft);
        this.drawPoints(rightPoints, this.bodyStyleRight);
        this.drawPoints(centerPoints, this.bodyStyleCenter);

        // Highlight key points with labels
        this.drawKeyBodyPoints(pointMap);
    }

    private drawKeyBodyPoints(pointMap: Map<string | number, Point2D>): void {
        // Label only important landmarks for clarity
        const keyPoints = ['body.nose', 'body.left_shoulder', 'body.right_shoulder', 'body.left_hip', 'body.right_hip'];

        for (const key of keyPoints) {
            const point = pointMap.get(key);
            if (point && this.isValidPoint(point)) {
                const style = this.getBodyStyleForSide(this.getBodySide(key));
                this.drawText(
                    key.replace('body.', '').replace('_', ' '),
                    point.x + 5,
                    point.y - 5,
                    8,
                    style.labelColor,
                    style.labelStroke,
                    1
                );
            }
        }
    }

    private drawBodyConnections(
        pointMap: Map<string | number, Point2D>,
    ): void {
        // Connections grouped by side for color coding
        const centerConnections = [
            ['body.nose', 'body.left_eye_inner'],
            ['body.nose', 'body.right_eye_inner'],
            ['body.mouth_left', 'body.mouth_right'],
            ['body.left_shoulder', 'body.right_shoulder'],
            ['body.left_hip', 'body.right_hip'],
        ];

        const leftConnections = [
            ['body.left_eye_inner', 'body.left_eye'],
            ['body.left_eye', 'body.left_eye_outer'],
            ['body.left_eye_outer', 'body.left_ear'],
            ['body.left_shoulder', 'body.left_hip'],
            ['body.left_shoulder', 'body.left_elbow'],
            ['body.left_elbow', 'body.left_wrist'],
            ['body.left_wrist', 'body.left_pinky'],
            ['body.left_wrist', 'body.left_index'],
            ['body.left_wrist', 'body.left_thumb'],
            ['body.left_index', 'body.left_pinky'],
            ['body.left_hip', 'body.left_knee'],
            ['body.left_knee', 'body.left_ankle'],
            ['body.left_ankle', 'body.left_heel'],
            ['body.left_heel', 'body.left_foot_index'],
            ['body.left_ankle', 'body.left_foot_index'],
        ];

        const rightConnections = [
            ['body.right_eye_inner', 'body.right_eye'],
            ['body.right_eye', 'body.right_eye_outer'],
            ['body.right_eye_outer', 'body.right_ear'],
            ['body.right_shoulder', 'body.right_hip'],
            ['body.right_shoulder', 'body.right_elbow'],
            ['body.right_elbow', 'body.right_wrist'],
            ['body.right_wrist', 'body.right_pinky'],
            ['body.right_wrist', 'body.right_index'],
            ['body.right_wrist', 'body.right_thumb'],
            ['body.right_index', 'body.right_pinky'],
            ['body.right_hip', 'body.right_knee'],
            ['body.right_knee', 'body.right_ankle'],
            ['body.right_ankle', 'body.right_heel'],
            ['body.right_heel', 'body.right_foot_index'],
            ['body.right_ankle', 'body.right_foot_index'],
        ];

        const groups: [string[][], DrawStyle][] = [
            [centerConnections, this.bodyStyleCenter],
            [leftConnections, this.bodyStyleLeft],
            [rightConnections, this.bodyStyleRight],
        ];

        for (const [connections, style] of groups) {
            for (const [start, end] of connections) {
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

        // Draw face contour highlights for key features
        this.drawFaceContour(points);
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
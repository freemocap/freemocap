// skeleton-overlay-renderer.ts
//
// Self-describing 2D skeleton overlay. Point names and connections ride the
// observation itself (overlay channels carry names inline; connections are the
// model's parent→child edges), so the renderer knows nothing about RTMPose,
// MediaPipe, or any specific tracker layout.

import {
    BaseOverlayRenderer,
    DrawStyle,
    Point2D,
} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import type {
    SkeletonObservation,
    SkeletonPoint,
} from "@/services/server/server-helpers/image-overlay/skeleton-types";

// Classification used for colour routing. Kept deliberately loose — any name
// containing "left" / "right" is treated as a side, otherwise center.
type Side = 'left' | 'right' | 'center';

function classifySide(name: string): Side {
    const lc = name.toLowerCase();
    if (lc.includes('left')) return 'left';
    if (lc.includes('right')) return 'right';
    return 'center';
}

function classifyHand(name: string): 'left_hand' | 'right_hand' | null {
    const lc = name.toLowerCase();
    if (lc.startsWith('left_hand') || lc.includes('left_hand_')) return 'left_hand';
    if (lc.startsWith('right_hand') || lc.includes('right_hand_')) return 'right_hand';
    return null;
}

function classifyFace(name: string): boolean {
    const lc = name.toLowerCase();
    return lc.startsWith('face') || lc.startsWith('face_') || lc.startsWith('face.');
}

export class SkeletonOverlayRenderer extends BaseOverlayRenderer {
    // --- Styles keyed by classification ---

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
     * Composite skeleton overlay onto frame. Points AND connections ride the
     * observation itself — it is fully self-describing.
     */
    public async compositeFrame(
        sourceBitmap: ImageBitmap,
        observation: SkeletonObservation | null,
    ): Promise<ImageBitmap> {
        this.prepareCanvas(
            sourceBitmap,
            observation?.image_width,
            observation?.image_height,
        );

        if (observation) {
            this.drawSkeletonOverlay(observation);
        }

        return this.createBitmap(sourceBitmap);
    }

    private drawSkeletonOverlay(observation: SkeletonObservation): void {
        this.ctx.save();

        const { scaleX, scaleY } = this;

        // Tracker keypoint detections — small dots, no connections.
        const pointMap = new Map<string, Point2D>();
        for (const p of observation.points) {
            pointMap.set(p.name, {
                x: p.x * scaleX,
                y: p.y * scaleY,
                id: p.name,
                visibility: p.visibility,
            });
        }
        this.drawAllPoints(pointMap);

        // Segment-origin landmarks — larger dots with the segment skeleton
        // connections drawn between them.
        const landmarks = observation.landmarks ?? [];
        const landmarkMap = new Map<string, Point2D>();
        for (const p of landmarks) {
            landmarkMap.set(p.name, {
                x: p.x * scaleX,
                y: p.y * scaleY,
                id: p.name,
                visibility: p.visibility,
            });
        }
        if (landmarkMap.size > 0) {
            this.drawConnections(landmarkMap, observation.connections ?? []);
            this.drawLandmarkPoints(landmarkMap);
        }

        // Debug: draw person bounding box.
        this.drawBbox(observation);

        this.drawStats(observation);

        this.ctx.restore();
    }

    private drawBbox(obs: SkeletonObservation): void {
        const { bbox_x1, bbox_y1, bbox_x2, bbox_y2, bbox_from_detector } = obs;
        if (bbox_x1 === undefined || bbox_y1 === undefined
            || bbox_x2 === undefined || bbox_y2 === undefined) return;
        if (!isFinite(bbox_x1) || !isFinite(bbox_y1)
            || !isFinite(bbox_x2) || !isFinite(bbox_y2)) return;

        const { scaleX, scaleY } = this;
        const x1 = bbox_x1 * scaleX;
        const y1 = bbox_y1 * scaleY;
        const x2 = bbox_x2 * scaleX;
        const y2 = bbox_y2 * scaleY;

        const color = bbox_from_detector ? '#00FF00' : '#FF8C00'; // green=YOLOX, orange=track
        const label = bbox_from_detector ? 'YOLOX' : 'track';
        const w = x2 - x1;
        const h = y2 - y1;
        if (w <= 0 || h <= 0) return;

        this.ctx.strokeStyle = color;
        this.ctx.lineWidth = 1.5;
        this.ctx.strokeRect(x1, y1, w, h);

        // Label at top-left of bbox.
        this.drawText(
            label,
            x1,
            Math.max(y1 - 4, 12),
            10,
            color,
            this.TEXT_STROKE,
            2,
        );
    }

    private styleFor(name: string): DrawStyle {
        if (classifyFace(name)) return this.faceStyle;
        const hand = classifyHand(name);
        if (hand === 'left_hand') return this.leftHandStyle;
        if (hand === 'right_hand') return this.rightHandStyle;
        const side = classifySide(name);
        if (side === 'left') return this.bodyStyleLeft;
        if (side === 'right') return this.bodyStyleRight;
        return this.bodyStyleCenter;
    }

    private drawConnections(
        pointMap: Map<string, Point2D>,
        connections: [string, string][],
    ): void {
        for (const [a, b] of connections) {
            const start = pointMap.get(a);
            const end = pointMap.get(b);
            if (!start || !end || !this.isValidPoint(start) || !this.isValidPoint(end)) continue;

            // Segment color picked from endpoint classification — if either
            // endpoint is hand/face/side the line takes that colour.
            const style = this.styleFor(a) === this.bodyStyleCenter ? this.styleFor(b) : this.styleFor(a);

            this.ctx.strokeStyle = style.lineColor;
            this.ctx.lineWidth = style.lineWidth;
            this.ctx.beginPath();
            this.ctx.moveTo(start.x, start.y);
            this.ctx.lineTo(end.x, end.y);
            this.ctx.stroke();
        }
    }

    /** The landmark markers: open circles (stroke only, nothing in the middle),
     *  slightly larger than the keypoint dots, so the fitted skeleton reads
     *  above the keypoint scatter without covering it. */
    private drawLandmarkPoints(pointMap: Map<string, Point2D>): void {
        const buckets = new Map<DrawStyle, Point2D[]>();
        for (const point of pointMap.values()) {
            const style = this.styleFor(point.id as string);
            const list = buckets.get(style);
            if (list) list.push(point);
            else buckets.set(style, [point]);
        }
        for (const [style, points] of buckets) {
            this.drawPoints(points, {...style, pointRadius: 5, fillPoint: false, pointColor: '#FFFFFF', pointStroke: '#FFFFFF'});
        }
    }

    /** The always-on stats block — a two-line legend mirroring the drawing
     *  convention: line 1 = a filled dot = "keypoints" + an open circle =
     *  "landmarks" (full words, no abbreviations), line 2 = the frame number.
     *  Stacked so it fits narrow (portrait) camera feeds. */
    private drawStats(observation: SkeletonObservation): void {
        const finite = (points: SkeletonPoint[]): number =>
            points.reduce((n, p) => n + (Number.isFinite(p.x) && Number.isFinite(p.y) ? 1 : 0), 0);
        const kp = finite(observation.points);
        const lm = finite(observation.landmarks ?? []);

        const fontSize = 11;
        const lineHeight = 17;
        const textWidth = (s: string): number => s.length * (fontSize * 0.62);
        const kpLabel = `${kp} keypoints`;
        const lmLabel = `${lm} landmarks`;
        const frameText = `frame ${observation.frame_number}`;

        const legendWidth = 16 + (9 + textWidth(kpLabel) + 14)
            + (9 + textWidth(lmLabel)) + 8;
        const bgWidth = Math.max(legendWidth, 16 + textWidth(frameText) + 8);

        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
        this.ctx.fillRect(6, 6, bgWidth, 8 + lineHeight * 2);

        const glyphY = 6 + lineHeight - 5;   // glyph center on line 1
        const line1Y = 6 + lineHeight;       // text baseline on line 1
        const line2Y = 6 + lineHeight * 2;   // text baseline on line 2

        let x = 14;

        // Filled dot glyph + "N keypoints".
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.beginPath();
        this.ctx.arc(x, glyphY, 3.5, 0, Math.PI * 2);
        this.ctx.fill();
        this.drawText(kpLabel, x + 9, line1Y, fontSize, '#DDDDDD', '#111111', 2);
        x += 9 + textWidth(kpLabel) + 14;

        // Open circle glyph + "N landmarks".
        this.ctx.strokeStyle = '#FFFFFF';
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.arc(x, glyphY, 3.5, 0, Math.PI * 2);
        this.ctx.stroke();
        this.drawText(lmLabel, x + 9, line1Y, fontSize, '#DDDDDD', '#111111', 2);

        // Line 2: frame number.
        this.drawText(frameText, 14, line2Y, fontSize, '#DDDDDD', '#111111', 2);
    }

    private drawAllPoints(pointMap: Map<string, Point2D>): void {
        // Bucket by style so we can call drawPoints with one style per batch.
        const buckets = new Map<DrawStyle, Point2D[]>();
        for (const point of pointMap.values()) {
            const style = this.styleFor(point.id as string);
            const list = buckets.get(style);
            if (list) list.push(point);
            else buckets.set(style, [point]);
        }
        for (const [style, points] of buckets) {
            this.drawPoints(points, style);
        }
    }
}

// skeleton-overlay-renderer.ts
//
// Schema-driven 2D skeleton overlay. Point names and connections come from a
// `TrackedObjectDefinition` pushed over the `tracker_schemas` handshake
// message. The renderer knows nothing about RTMPose, MediaPipe, or any
// specific landmark layout — it draws whatever the active schema advertises.

import {
    BaseOverlayRenderer,
    DrawStyle,
    Point2D,
} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import {TrackedObjectDefinition} from "@/services/server/server-helpers/tracked-object-definition";

export interface SkeletonPoint {
    name: string;
    x: number;
    y: number;
    z?: number;
    visibility?: number;
}

export interface SkeletonObservation {
    message_type: 'skeleton_overlay';
    camera_id: string;
    frame_number: number;
    tracker_id: string;
    image_width: number;
    image_height: number;
    points: SkeletonPoint[];
    // Debug: person bounding box in image pixel coords (xyxy). NaN = absent.
    bbox_x1?: number;
    bbox_y1?: number;
    bbox_x2?: number;
    bbox_y2?: number;
    bbox_from_detector?: boolean;
}

// Debug HUD (frame number + tracker/point counts) drawn on top of every camera
// feed. It's redrawn every frame per camera — two stroked+filled text draws plus
// a font set each — which showed up as ~12% of main-thread time during streaming.
// Off by default; flip to true when debugging the overlay pipeline.
const SHOW_SKELETON_DEBUG_HUD = false;

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
    private schema: TrackedObjectDefinition | null = null;

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

    /** Provide or update the tracker schema that drives connection lookup. */
    public setSchema(schema: TrackedObjectDefinition | null): void {
        this.schema = schema;
    }

    /**
     * Composite skeleton overlay onto frame. Points come from the observation;
     * connections come from `this.schema` (resolved by name).
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

        const pointMap = new Map<string, Point2D>();
        for (const p of observation.points) {
            pointMap.set(p.name, {
                x: p.x * scaleX,
                y: p.y * scaleY,
                id: p.name,
                visibility: p.visibility,
            });
        }

        // Connections first (underneath the points), then points.
        if (this.schema && this.schema.name === observation.tracker_id) {
            this.drawConnections(pointMap, this.schema);
        }

        this.drawAllPoints(pointMap);

        // Debug: draw person bounding box.
        this.drawBbox(observation);

        if (SHOW_SKELETON_DEBUG_HUD) {
            this.drawInfo(observation);
        }

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
        schema: TrackedObjectDefinition,
    ): void {
        for (const [a, b] of schema.connections) {
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

    private drawInfo(observation: SkeletonObservation): void {
        const {points, frame_number, tracker_id} = observation;

        this.ctx.fillStyle = this.INFO_BG;
        this.ctx.fillRect(5, 5, 500, 60);

        this.drawText(
            `Frame: ${frame_number}`,
            10,
            25,
            14,
            this.TEXT_COLOR,
            this.TEXT_STROKE,
            2,
        );

        const schemaSuffix = this.schema
            ? (this.schema.name === tracker_id ? '' : ' (schema mismatch!)')
            : ' (schema pending)';
        this.drawText(
            `Tracker: ${tracker_id} — points: ${points.length}${schemaSuffix}`,
            10,
            50,
            14,
            points.length > 0 ? '#00FF00' : '#FF4444',
            this.TEXT_STROKE,
            2,
        );
    }
}

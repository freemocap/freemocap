// skeleton-overlay-renderer.ts
//
// Self-describing 2D skeleton overlay. Point names and connections ride the
// observation itself (overlay channels carry names inline; connections are the
// model's parent→child edges), so the renderer knows nothing about RTMPose,
// MediaPipe, or any specific tracker layout.

import {
    BaseOverlayRenderer,
    DrawStyle,

} from "@/services/server/server-helpers/image-overlay/image-overlay-system";
import type {SkeletonObservation} from './skeleton-types';
import {OverlayLayer, type OverlayFrame} from '../../transport/frame-types';
import {snapshotEqual} from '../../transport/snapshot-equality';

interface PreparedOverlay {
    layer: OverlayLayer;
    names: readonly string[];
    columns: readonly string[];
    connections: readonly (readonly [string, string])[];
    styles: DrawStyle[];
    edges: Int32Array;
    edgeStyles: DrawStyle[];
    offsets: number[];
}
// Classification used for colour routing. Kept deliberately loose — any name
// containing "left" / "right" is treated as a side, otherwise center.
type Side = 'left' | 'right' | 'center';

function classifySide(name: string): Side {
    const lc = name.toLowerCase();
    if (lc.includes('left') || lc.endsWith('.l')) return 'left';
    if (lc.includes('right') || lc.endsWith('.r')) return 'right';
    return 'center';
}

function classifyHand(name: string): 'left_hand' | 'right_hand' | null {
    const lc = name.toLowerCase();
    // The hand segment + the finger segments (thumb/index/middle/ring/little)
    // are all hand parts; the tracker's hand keypoints carry `left_hand_` too.
    if (!/hand|thumb|index|middle|ring|pinky|finger|little/.test(lc)) return null;
    if (lc.startsWith('left_') || lc.endsWith('.l')) return 'left_hand';
    if (lc.startsWith('right_') || lc.endsWith('.r')) return 'right_hand';
    return null;
}

function classifyFace(name: string): boolean {
    const lc = name.toLowerCase();
    // Face segment names (eyes / ears / nose / jaw / mouth) + the tracker's
    // face_* keypoint prefix.
    return /eye|ear|nose|jaw|mouth/.test(lc) || lc.startsWith('face');
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
        pointRadius: 2,
        lineColor: '#FF6400',
        lineWidth: 1,
        labelColor: '#FF6400',
        labelStroke: this.TEXT_STROKE,
        labelFontSize: 8,
        showLabels: false,
    };

    private readonly leftHandStyle: DrawStyle = {
        pointColor: '#00AAFF',
        pointStroke: '#0066AA',
        pointRadius: 2,
        lineColor: '#00AAFF',
        lineWidth: 1,
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

    private readonly preparedLayers: PreparedOverlay[] = [];
    private layerIndex = 0;

    private prepareLayer(values: OverlayFrame, connections: readonly (readonly [string, string])[] = []): PreparedOverlay {
        const position = this.layerIndex++;
        const previous = this.preparedLayers[position];
        if (values.data.length !== values.names.length * values.columns.length)
            throw new Error('Camera overlay values do not match their declared layout');
        if (previous && previous.layer === values.layer && snapshotEqual(previous.names, values.names) && snapshotEqual(previous.columns, values.columns)
            && snapshotEqual(previous.connections, connections)) return previous;
        if (new Set(values.columns).size !== values.columns.length) throw new Error('Camera overlay components must be unique');
        const components = values.layer === OverlayLayer.BOXES ? ['x1', 'y1', 'x2', 'y2', 'confidence', 'detector_ran'] : ['x', 'y', 'visibility'];
        const offsets = components.map(component => values.columns.indexOf(component));
        if (offsets.some(offset => offset < 0)) throw new Error('Camera overlay is missing required components');
        const styles = values.names.map(name => this.styleFor(name));
        const rowsByName = new Map(values.names.map((name, row) => [name, row]));
        const edges = new Int32Array(connections.length * 2), edgeStyles: DrawStyle[] = [];
        connections.forEach(([first, second], index) => {
            edges[index * 2] = rowsByName.get(first) ?? -1;
            edges[index * 2 + 1] = rowsByName.get(second) ?? -1;
            const firstStyle = this.styleFor(first);
            edgeStyles.push(firstStyle === this.bodyStyleCenter ? this.styleFor(second) : firstStyle);
        });
        return this.preparedLayers[position] = {layer: values.layer, names: values.names, columns: values.columns, connections, styles, edges, edgeStyles, offsets};
    }

    private drawSkeletonOverlay(observation: SkeletonObservation): void {
        this.ctx.save();
        try {
            this.layerIndex = 0;
            let keypointCount = 0, landmarkCount = 0;
            for (const values of observation.pointLayers) keypointCount += this.drawPointLayer(values, false);
            for (const layer of observation.landmarkLayers) landmarkCount += this.drawPointLayer(layer.values, true, layer.connections);
            for (const values of observation.boxLayers) this.drawBoxLayer(values);
            this.preparedLayers.length = this.layerIndex;
            this.drawStats(observation, keypointCount, landmarkCount);
        } finally {
            this.ctx.restore();
        }
    }

    private drawPointLayer(values: OverlayFrame, landmarks: boolean, connections: readonly (readonly [string, string])[] = []): number {
        const prepared = this.prepareLayer(values, connections);
        const {data, names, columns} = values, stride = columns.length;
        const [xOffset, yOffset] = prepared.offsets;
        for (let edge = 0; edge < prepared.edgeStyles.length; edge++) {
            const first = prepared.edges[edge * 2], second = prepared.edges[edge * 2 + 1];
            if (first < 0 || second < 0) continue;
            const x1 = data[first * stride + xOffset] * this.scaleX, y1 = data[first * stride + yOffset] * this.scaleY;
            const x2 = data[second * stride + xOffset] * this.scaleX, y2 = data[second * stride + yOffset] * this.scaleY;
            if (!Number.isFinite(x1) || !Number.isFinite(y1) || !Number.isFinite(x2) || !Number.isFinite(y2)) continue;
            const style = prepared.edgeStyles[edge];
            this.ctx.strokeStyle = style.lineColor; this.ctx.lineWidth = style.lineWidth;
            this.ctx.beginPath(); this.ctx.moveTo(x1, y1); this.ctx.lineTo(x2, y2); this.ctx.stroke();
        }
        let finiteCount = 0;
        for (let row = 0; row < names.length; row++) {
            const x = data[row * stride + xOffset] * this.scaleX, y = data[row * stride + yOffset] * this.scaleY;
            if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
            finiteCount++;
            const style = prepared.styles[row];
            this.ctx.beginPath(); this.ctx.arc(x, y, style.pointRadius, 0, Math.PI * 2);
            if (landmarks) {this.ctx.strokeStyle = style.pointColor; this.ctx.lineWidth = 2; this.ctx.stroke();}
            else {this.ctx.fillStyle = style.pointColor; this.ctx.fill();}
        }
        return finiteCount;
    }

    private drawBoxLayer(values: OverlayFrame): void {
        const prepared = this.prepareLayer(values), stride = values.columns.length;
        const [left, top, right, bottom, confidenceOffset, detectorOffset] = prepared.offsets;
        for (let row = 0; row < values.names.length; row++) {
            const offset = row * stride, data = values.data;
            const x1 = data[offset + left] * this.scaleX, y1 = data[offset + top] * this.scaleY;
            const x2 = data[offset + right] * this.scaleX, y2 = data[offset + bottom] * this.scaleY;
            if (!Number.isFinite(x1) || !Number.isFinite(y1) || !Number.isFinite(x2) || !Number.isFinite(y2) || x2 <= x1 || y2 <= y1) continue;
            const color = data[offset + detectorOffset] >= 0.5 ? '#00FF00' : '#FF8C00';
            const confidence = data[offset + confidenceOffset], name = values.names[row];
            const label = Number.isFinite(confidence) ? `${name} ${confidence.toFixed(2)}` : name;
            this.ctx.strokeStyle = color; this.ctx.lineWidth = 1.5; this.ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
            this.drawText(label, x1, Math.max(y1 - 4, 12), 10, color, this.TEXT_STROKE, 2);
        }
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

    /** The always-on stats block — a vertical column: a filled dot =
     *  "N keypoints", an open circle = "N landmarks", then the frame number.
     *  Stacked so it reads cleanly and fits narrow (portrait) camera feeds. */
    private drawStats(observation: SkeletonObservation, kp: number, lm: number): void {
        const fontSize = 11;
        const lineHeight = 16;
        const pad = 8;
        const glyphRadius = 3;
        const glyphX = 6 + pad + glyphRadius;
        const textX = glyphX + glyphRadius + 6;

        const rows: { glyph: 'dot' | 'ring' | null; label: string }[] = [
            { glyph: 'dot', label: `${kp} keypoints` },
            { glyph: 'ring', label: `${lm} landmarks` },
            { glyph: null, label: `frame ${observation.frame_number}` },
        ];

        const textWidth = (s: string): number => s.length * (fontSize * 0.6);
        const maxLabelWidth = Math.max(...rows.map((r) => textWidth(r.label)));
        const bgWidth = textX + maxLabelWidth + pad;
        const bgHeight = pad * 2 + rows.length * lineHeight;

        this.ctx.fillStyle = 'rgba(0, 0, 0, 0.55)';
        this.ctx.fillRect(6, 6, bgWidth, bgHeight);

        rows.forEach((row, i) => {
            const rowY = 6 + pad + i * lineHeight + lineHeight / 2;

            if (row.glyph === 'dot') {
                this.ctx.fillStyle = '#FFFFFF';
                this.ctx.beginPath();
                this.ctx.arc(glyphX, rowY, glyphRadius, 0, Math.PI * 2);
                this.ctx.fill();
            } else if (row.glyph === 'ring') {
                this.ctx.strokeStyle = '#FFFFFF';
                this.ctx.lineWidth = 2;
                this.ctx.beginPath();
                this.ctx.arc(glyphX, rowY, glyphRadius, 0, Math.PI * 2);
                this.ctx.stroke();
            }

            this.drawText(row.label, textX, rowY, fontSize, '#DDDDDD', '#111111', 2);
        });
    }

}

// keypoints-binary-parser.ts
/**
 * Decodes the binary keypoints websocket message produced by
 * `freemocap/core/viz/frontend_keypoints_serializer.py`.
 *
 * Returns typed-array views into the original ArrayBuffer (no copies). Hold
 * onto the buffer while you use the views. For step 1 of the JSON→binary
 * refactor we also expose a helper that materializes the legacy
 * `Record<string, Point3d>` shape so the existing renderer subscription
 * contract can stay unchanged. A follow-up will hand the typed arrays to the
 * renderer directly and `postMessage(buf, [buf])` them to web workers.
 */
import {
    BLOCK_KIND,
    BlockKind,
    DTYPE_CODE,
    DtypeCode,
    KEYPOINTS_BLOCK_HEADER_FIELDS,
    KEYPOINTS_BLOCK_HEADER_SIZE,
    KEYPOINTS_MESSAGE_TYPE,
    KEYPOINTS_PAYLOAD_FOOTER_SIZE,
    KEYPOINTS_PAYLOAD_HEADER_FIELDS,
    KEYPOINTS_PAYLOAD_HEADER_SIZE,
    dtypeByteSize,
    readAsciiField,
} from "./keypoints-protocol";

export interface KeypointBlock {
    kind: BlockKind;
    trackerId: string;
    cameraId: string;     // "" for 3D blocks
    numPoints: number;
    dims: 2 | 3;
    dtypeCode: DtypeCode;
    /**
     * Interleaved [x, y, (z,) visibility] view over the original buffer.
     * Length = numPoints * (dims + 1). Missing points have NaN coords and
     * visibility 0.
     */
    interleaved: Float32Array | Float64Array;
}

export interface ParsedKeypointsMessage {
    frameNumber: number;
    blocks: KeypointBlock[];
}

/** Returns `true` if the buffer's first byte identifies it as a keypoints message. */
export function isKeypointsMessage(buf: ArrayBuffer): boolean {
    if (buf.byteLength < 1) return false;
    return new Uint8Array(buf, 0, 1)[0] === KEYPOINTS_MESSAGE_TYPE.KEYPOINTS_PAYLOAD_HEADER;
}

export function parseKeypointsMessage(buf: ArrayBuffer): ParsedKeypointsMessage {
    if (buf.byteLength < KEYPOINTS_PAYLOAD_HEADER_SIZE + KEYPOINTS_PAYLOAD_FOOTER_SIZE) {
        throw new Error(`Keypoints buffer too small: ${buf.byteLength} bytes`);
    }
    const view = new DataView(buf);
    const headerType = view.getUint8(KEYPOINTS_PAYLOAD_HEADER_FIELDS.message_type.offset);
    if (headerType !== KEYPOINTS_MESSAGE_TYPE.KEYPOINTS_PAYLOAD_HEADER) {
        throw new Error(`Unexpected payload header message_type=${headerType}`);
    }

    // BigInt → Number: frame numbers fit in JS safe-integer range for any
    // realistic session (>200 years at 60 fps).
    const frameNumberBig = view.getBigInt64(KEYPOINTS_PAYLOAD_HEADER_FIELDS.frame_number.offset, true);
    const frameNumber = Number(frameNumberBig);
    const numBlocks = view.getUint32(KEYPOINTS_PAYLOAD_HEADER_FIELDS.num_blocks.offset, true);

    const blocks: KeypointBlock[] = [];
    let cursor = KEYPOINTS_PAYLOAD_HEADER_SIZE;

    for (let b = 0; b < numBlocks; b++) {
        if (cursor + KEYPOINTS_BLOCK_HEADER_SIZE > buf.byteLength) {
            throw new Error(`Block ${b} header runs past end of buffer`);
        }
        const blockView = new DataView(buf, cursor, KEYPOINTS_BLOCK_HEADER_SIZE);
        const messageType = blockView.getUint8(KEYPOINTS_BLOCK_HEADER_FIELDS.message_type.offset);
        if (messageType !== KEYPOINTS_MESSAGE_TYPE.KEYPOINTS_BLOCK_HEADER) {
            throw new Error(`Block ${b} has unexpected message_type=${messageType}`);
        }
        const kind = blockView.getUint8(KEYPOINTS_BLOCK_HEADER_FIELDS.block_kind.offset) as BlockKind;
        const dtypeCode = blockView.getUint8(KEYPOINTS_BLOCK_HEADER_FIELDS.dtype_code.offset) as DtypeCode;
        const dims = blockView.getUint8(KEYPOINTS_BLOCK_HEADER_FIELDS.dims.offset);
        if (dims !== 2 && dims !== 3) {
            throw new Error(`Block ${b} has unsupported dims=${dims}`);
        }
        const cameraId = readAsciiField(blockView, KEYPOINTS_BLOCK_HEADER_FIELDS.camera_id.offset, KEYPOINTS_BLOCK_HEADER_FIELDS.camera_id.size);
        const trackerId = readAsciiField(blockView, KEYPOINTS_BLOCK_HEADER_FIELDS.tracker_id.offset, KEYPOINTS_BLOCK_HEADER_FIELDS.tracker_id.size);
        const numPoints = blockView.getUint32(KEYPOINTS_BLOCK_HEADER_FIELDS.num_points.offset, true);
        const dataByteLength = blockView.getUint32(KEYPOINTS_BLOCK_HEADER_FIELDS.data_byte_length.offset, true);

        const expectedDataBytes = numPoints * (dims + 1) * dtypeByteSize(dtypeCode);
        if (dataByteLength !== expectedDataBytes) {
            throw new Error(
                `Block ${b} data_byte_length=${dataByteLength} does not match expected ${expectedDataBytes}`,
            );
        }

        cursor += KEYPOINTS_BLOCK_HEADER_SIZE;
        if (cursor + dataByteLength > buf.byteLength) {
            throw new Error(`Block ${b} data runs past end of buffer`);
        }

        const elementCount = numPoints * (dims + 1);
        const interleaved = dtypeCode === DTYPE_CODE.FLOAT32
            ? new Float32Array(buf, cursor, elementCount)
            : new Float64Array(buf, cursor, elementCount);

        blocks.push({
            kind,
            trackerId,
            cameraId,
            numPoints,
            dims: dims as 2 | 3,
            dtypeCode,
            interleaved,
        });
        cursor += dataByteLength;
    }

    if (cursor + KEYPOINTS_PAYLOAD_FOOTER_SIZE > buf.byteLength) {
        throw new Error(`Footer runs past end of buffer (cursor=${cursor}, total=${buf.byteLength})`);
    }
    const footerType = view.getUint8(cursor + KEYPOINTS_PAYLOAD_HEADER_FIELDS.message_type.offset);
    if (footerType !== KEYPOINTS_MESSAGE_TYPE.KEYPOINTS_PAYLOAD_FOOTER) {
        throw new Error(`Footer has unexpected message_type=${footerType}`);
    }

    return { frameNumber, blocks };
}

export interface Point3dLike { x: number; y: number; z: number; }

/**
 * Materialize a `Record<string, Point3d>` keyed by point name from a 3D block.
 * Skips rows where visibility is 0 or any coordinate is NaN — matches the
 * sparse-dict semantics of the legacy JSON path. Allocates one object per
 * visible point; intended as a drop-in replacement for the JSON dispatch
 * path during step 1 of the refactor.
 */
export function blockToPointDict(
    block: KeypointBlock,
    pointNames: ReadonlyArray<string>,
): Record<string, Point3dLike> {
    if (block.dims !== 3) return {};
    const out: Record<string, Point3dLike> = {};
    const arr = block.interleaved;
    const stride = block.dims + 1;
    const limit = Math.min(block.numPoints, pointNames.length);
    for (let i = 0; i < limit; i++) {
        const off = i * stride;
        const visibility = arr[off + 3];
        if (!visibility) continue;
        const x = arr[off + 0];
        const y = arr[off + 1];
        const z = arr[off + 2];
        if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) continue;
        out[pointNames[i]] = { x, y, z };
    }
    return out;
}

export { BLOCK_KIND };

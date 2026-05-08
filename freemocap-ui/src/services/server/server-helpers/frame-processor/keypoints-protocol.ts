// keypoints-protocol.ts
/**
 * Binary protocol for the keypoints websocket message.
 * Mirrors freemocap/api/websocket/binary_keypoints_protocol.py — all field
 * offsets and sizes here MUST match the numpy dtype layout produced with
 * `align=True` on the Python side. See test_binary_keypoints_protocol.py.
 *
 * Wire layout:
 *   PAYLOAD_HEADER (24B)
 *   For each block:
 *     BLOCK_HEADER (60B)
 *     BLOCK_DATA   (num_points * (dims + 1) * sizeof(dtype) bytes)
 *   PAYLOAD_FOOTER (24B)
 *
 * The first byte of every binary websocket frame carries `message_type`,
 * which we demultiplex against the existing JPEG image protocol (which uses
 * 0/1/2 — we use 3/4/5 here).
 */

export const KEYPOINTS_MESSAGE_TYPE = {
    KEYPOINTS_PAYLOAD_HEADER: 3,
    KEYPOINTS_BLOCK_HEADER: 4,
    KEYPOINTS_PAYLOAD_FOOTER: 5,
} as const;

export const BLOCK_KIND = {
    KEYPOINTS_RAW_3D: 0,
    KEYPOINTS_FILTERED_3D: 1,
    SKELETON_OVERLAY_2D: 2,
    CHARUCO_OVERLAY_2D: 3,
} as const;

export type BlockKind = typeof BLOCK_KIND[keyof typeof BLOCK_KIND];

export const DTYPE_CODE = {
    FLOAT32: 0,
    FLOAT64: 1,
} as const;

export type DtypeCode = typeof DTYPE_CODE[keyof typeof DTYPE_CODE];

// Fixed string field widths (must match Python CAMERA_ID_BYTES / TRACKER_ID_BYTES)
export const CAMERA_ID_BYTES = 16;
export const TRACKER_ID_BYTES = 32;

// PAYLOAD header / footer (numpy dtype with align=True):
//   message_type (u1) at 0
//   <7B padding>
//   frame_number (i8) at 8
//   num_blocks   (u4) at 16
//   <4B padding>
export const KEYPOINTS_PAYLOAD_HEADER_FIELDS = {
    message_type: { offset: 0,  size: 1 },
    frame_number: { offset: 8,  size: 8 },
    num_blocks:   { offset: 16, size: 4 },
} as const;

export const KEYPOINTS_PAYLOAD_HEADER_SIZE = 24;
export const KEYPOINTS_PAYLOAD_FOOTER_SIZE = 24;

// BLOCK header (numpy dtype with align=True):
//   message_type (u1)  at 0
//   block_kind   (u1)  at 1
//   dtype_code   (u1)  at 2
//   dims         (u1)  at 3
//   camera_id    (S16) at 4   -> ends at 20
//   tracker_id   (S32) at 20  -> ends at 52
//   num_points   (u4)  at 52
//   data_byte_length (u4) at 56
//   <0B padding>  itemsize 60
export const KEYPOINTS_BLOCK_HEADER_FIELDS = {
    message_type:     { offset: 0,  size: 1 },
    block_kind:       { offset: 1,  size: 1 },
    dtype_code:       { offset: 2,  size: 1 },
    dims:             { offset: 3,  size: 1 },
    camera_id:        { offset: 4,  size: CAMERA_ID_BYTES },
    tracker_id:       { offset: 4 + CAMERA_ID_BYTES, size: TRACKER_ID_BYTES },
    num_points:       { offset: 4 + CAMERA_ID_BYTES + TRACKER_ID_BYTES, size: 4 },
    data_byte_length: { offset: 8 + CAMERA_ID_BYTES + TRACKER_ID_BYTES, size: 4 },
} as const;

export const KEYPOINTS_BLOCK_HEADER_SIZE = 12 + CAMERA_ID_BYTES + TRACKER_ID_BYTES; // 60

export function dtypeByteSize(code: DtypeCode): number {
    switch (code) {
        case DTYPE_CODE.FLOAT32: return 4;
        case DTYPE_CODE.FLOAT64: return 8;
    }
}

/** Read a fixed-width null-padded ASCII string from a DataView. */
export function readAsciiField(view: DataView, offset: number, size: number): string {
    const bytes = new Uint8Array(view.buffer, view.byteOffset + offset, size);
    let end = bytes.indexOf(0);
    if (end === -1) end = size;
    let s = "";
    for (let i = 0; i < end; i++) s += String.fromCharCode(bytes[i]);
    return s;
}

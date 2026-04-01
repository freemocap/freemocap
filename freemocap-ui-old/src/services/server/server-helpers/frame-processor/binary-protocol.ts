// binary-protocol.ts
/**
 * Binary protocol definition for frame payloads
 * Matches the Python FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE and FRONTEND_FRAME_HEADER_DTYPE
 * WITH align=True (includes padding for natural alignment)
 * All offsets and sizes are in bytes
 */

// Message type constants (matches Python MessageType class)
export const MESSAGE_TYPE = {
    PAYLOAD_HEADER: 0,
    FRAME_METADATA: 1,
    PAYLOAD_FOOTER: 2,
} as const;

// Field sizes (in bytes)
const FIELD_SIZES = {
    // Primitive types
    U1: 1,      // unsigned 8-bit
    I4: 4,      // signed 32-bit integer
    I8: 8,      // signed 64-bit integer
    S16: 16,    // 16-byte ASCII string (for camera_id)
} as const;

// Payload header structure (matches FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE with align=True)
// Structure with padding:
//   message_type (1 byte) + padding (7 bytes) + frame_number (8 bytes) + number_of_cameras (4 bytes) + padding (4 bytes)
export const PAYLOAD_HEADER_FIELDS = {
    message_type:      { offset: 0,  size: FIELD_SIZES.U1, type: 'uint8' },
    // 7 bytes padding here for 8-byte alignment of frame_number
    frame_number:      { offset: 8,  size: FIELD_SIZES.I8, type: 'int64' },
    number_of_cameras: { offset: 16, size: FIELD_SIZES.I4, type: 'int32' },
    // 4 bytes padding here for struct alignment
} as const;

export const PAYLOAD_HEADER_SIZE = 24; // Total: 1 + 7 padding + 8 + 4 + 4 padding

// Frame header structure (matches FRONTEND_FRAME_HEADER_DTYPE with align=True)
// Structure with padding:
//   message_type (1 byte) + padding (7 bytes) + frame_number (8 bytes) + camera_id (16 bytes) +
//   camera_index (4 bytes) + image_width (4 bytes) + image_height (4 bytes) +
//   color_channels (4 bytes) + jpeg_string_length (4 bytes) + padding (4 bytes)
export const FRAME_HEADER_FIELDS = {
    message_type:        { offset: 0,  size: FIELD_SIZES.U1,  type: 'uint8' },
    // 7 bytes padding here for 8-byte alignment of frame_number
    frame_number:        { offset: 8,  size: FIELD_SIZES.I8,  type: 'int64' },
    camera_id:           { offset: 16, size: FIELD_SIZES.S16, type: 'ascii' },
    camera_index:        { offset: 32, size: FIELD_SIZES.I4,  type: 'int32' },
    image_width:         { offset: 36, size: FIELD_SIZES.I4,  type: 'int32' },
    image_height:        { offset: 40, size: FIELD_SIZES.I4,  type: 'int32' },
    color_channels:      { offset: 44, size: FIELD_SIZES.I4,  type: 'int32' },
    jpeg_string_length:  { offset: 48, size: FIELD_SIZES.I4,  type: 'int32' },
    // 4 bytes padding here for struct alignment
} as const;

export const FRAME_HEADER_SIZE = 56; // Total: 1 + 7 padding + 8 + 16 + 4 + 4 + 4 + 4 + 4 + 4 padding

// Payload footer structure (matches FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE with align=True)
export const PAYLOAD_FOOTER_FIELDS = {
    message_type:      { offset: 0,  size: FIELD_SIZES.U1, type: 'uint8' },
    // 7 bytes padding here for 8-byte alignment of frame_number
    frame_number:      { offset: 8,  size: FIELD_SIZES.I8, type: 'int64' },
    number_of_cameras: { offset: 16, size: FIELD_SIZES.I4, type: 'int32' },
    // 4 bytes padding here for struct alignment
} as const;

export const PAYLOAD_FOOTER_SIZE = 24; // Total: 1 + 7 padding + 8 + 4 + 4 padding

// Helper type definitions
export type FieldType = 'uint8' | 'int32' | 'int64' | 'ascii';

export interface FieldDefinition {
    offset: number;
    size: number;
    type: FieldType;
}

export type MessageType = typeof MESSAGE_TYPE[keyof typeof MESSAGE_TYPE];

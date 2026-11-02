// images/image-payload.ts
//
// Reader for SkellyCam's multi-camera image payload: the bytes a frame message
// carries in its `image` field, one synchronized JPEG per camera. The layout is
// owned by SkellyCam (FRONTEND_PAYLOAD_HEADER_FOOTER_DTYPE and
// FRONTEND_FRAME_HEADER_DTYPE in skellycam/core/types/frontend_payload_bytearray.py):
// little-endian numpy structs with align=True padding.
//
//   payload header  24 bytes: message_type 0, frame_number, number_of_cameras
//   per camera      56 bytes: message_type 1, frame_number, camera_id, camera_index,
//                   image_width, image_height, color_channels, jpeg_string_length,
//                   followed by that many JPEG bytes
//   payload footer  24 bytes: the header repeated with message_type 2
//
// Reading is pure and runs anywhere (Node, browser, worker); decoding the JPEGs
// needs browser APIs and lives in jpeg.ts.

export const IMAGE_PAYLOAD_MESSAGE_TYPE = {
    PAYLOAD_HEADER: 0,
    FRAME_METADATA: 1,
    PAYLOAD_FOOTER: 2,
} as const;

export type ImagePayloadFieldType = "uint8" | "int32" | "int64" | "ascii";

export interface ImagePayloadField {
    offset: number;
    size: number;
    type: ImagePayloadFieldType;
}

/** Payload header and footer: message_type, 7 padding bytes, frame_number, number_of_cameras, 4 padding bytes. */
export const IMAGE_PAYLOAD_HEADER_FIELDS = {
    message_type: { offset: 0, size: 1, type: "uint8" },
    frame_number: { offset: 8, size: 8, type: "int64" },
    number_of_cameras: { offset: 16, size: 4, type: "int32" },
} as const satisfies Record<string, ImagePayloadField>;

export const IMAGE_PAYLOAD_HEADER_SIZE = 24;
export const IMAGE_PAYLOAD_FOOTER_FIELDS = IMAGE_PAYLOAD_HEADER_FIELDS;
export const IMAGE_PAYLOAD_FOOTER_SIZE = IMAGE_PAYLOAD_HEADER_SIZE;

/** Per-camera header: message_type, 7 padding bytes, then the fields below, 4 padding bytes. */
export const IMAGE_FRAME_HEADER_FIELDS = {
    message_type: { offset: 0, size: 1, type: "uint8" },
    frame_number: { offset: 8, size: 8, type: "int64" },
    camera_id: { offset: 16, size: 16, type: "ascii" },
    camera_index: { offset: 32, size: 4, type: "int32" },
    image_width: { offset: 36, size: 4, type: "int32" },
    image_height: { offset: 40, size: 4, type: "int32" },
    color_channels: { offset: 44, size: 4, type: "int32" },
    jpeg_string_length: { offset: 48, size: 4, type: "int32" },
} as const satisfies Record<string, ImagePayloadField>;

export const IMAGE_FRAME_HEADER_SIZE = 56;

/** One camera's image as declared by its header. */
export interface PayloadImage {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    /** The JPEG bytes: a view sharing the payload's buffer, so transferring or
     *  detaching that buffer invalidates it. */
    jpeg: Uint8Array<ArrayBuffer>;
}

export interface ImagePayload {
    frameNumber: number;
    images: PayloadImage[];
}

const asciiDecoder = new TextDecoder("ascii");

/** Read a whole image payload. Throws when any part is malformed: a payload is
 *  produced atomically, so a partial or inconsistent one is a defect, never
 *  something to render. The JPEG bytes are returned as views, not copies. */
export function readImagePayload(data: ArrayBuffer | Uint8Array): ImagePayload {
    const bytes = data instanceof Uint8Array
        ? new Uint8Array(data.buffer as ArrayBuffer, data.byteOffset, data.byteLength)
        : new Uint8Array(data);
    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const ensureBytes = (offset: number, length: number, what: string): void => {
        if (offset + length > bytes.byteLength) {
            throw new Error(`Image payload truncated: ${what} needs ${length} bytes at offset ${offset} of ${bytes.byteLength}`);
        }
    };

    ensureBytes(0, IMAGE_PAYLOAD_HEADER_SIZE, "payload header");
    if (view.getUint8(IMAGE_PAYLOAD_HEADER_FIELDS.message_type.offset) !== IMAGE_PAYLOAD_MESSAGE_TYPE.PAYLOAD_HEADER) {
        throw new Error("Image payload does not start with a payload header");
    }
    const frameNumber = Number(view.getBigInt64(IMAGE_PAYLOAD_HEADER_FIELDS.frame_number.offset, true));
    if (!Number.isSafeInteger(frameNumber)) throw new Error('Image frame number exceeds exact JavaScript integer range');
    const cameraCount = view.getInt32(IMAGE_PAYLOAD_HEADER_FIELDS.number_of_cameras.offset, true);
    if (cameraCount < 1) throw new Error(`Image payload declares ${cameraCount} cameras`);

    const images: PayloadImage[] = [];
    let offset = IMAGE_PAYLOAD_HEADER_SIZE;
    for (let camera = 0; camera < cameraCount; camera++) {
        ensureBytes(offset, IMAGE_FRAME_HEADER_SIZE, `camera ${camera} header`);
        const field = (name: keyof typeof IMAGE_FRAME_HEADER_FIELDS) => offset + IMAGE_FRAME_HEADER_FIELDS[name].offset;
        if (view.getUint8(field("message_type")) !== IMAGE_PAYLOAD_MESSAGE_TYPE.FRAME_METADATA) {
            throw new Error(`Image payload camera ${camera} has no frame header`);
        }
        const imageFrameNumber = Number(view.getBigInt64(field("frame_number"), true));
        if (imageFrameNumber !== frameNumber) {
            throw new Error(`Image payload camera ${camera} is frame ${imageFrameNumber}, not ${frameNumber}`);
        }
        const idBytes = bytes.subarray(field("camera_id"), field("camera_id") + IMAGE_FRAME_HEADER_FIELDS.camera_id.size);
        const idLength = idBytes.indexOf(0);
        const cameraId = asciiDecoder.decode(idLength < 0 ? idBytes : idBytes.subarray(0, idLength));
        const jpegLength = view.getInt32(field("jpeg_string_length"), true);
        if (idBytes.subarray(0, idLength < 0 ? idBytes.length : idLength).some(byte => byte > 127)) {
            throw new Error('Image camera ID must be ASCII');
        }
        if (cameraId.length === 0) throw new Error(`Image payload camera ${camera} has an empty ID`);
        if (jpegLength < 1) throw new Error(`Image payload camera ${cameraId} declares ${jpegLength} JPEG bytes`);
        const jpegStart = offset + IMAGE_FRAME_HEADER_SIZE;
        ensureBytes(jpegStart, jpegLength, `camera ${cameraId} JPEG`);
        images.push({
            cameraId,
            cameraIndex: view.getInt32(field("camera_index"), true),
            frameNumber,
            width: view.getInt32(field("image_width"), true),
            height: view.getInt32(field("image_height"), true),
            colorChannels: view.getInt32(field("color_channels"), true),
            jpeg: new Uint8Array(bytes.buffer, bytes.byteOffset + jpegStart, jpegLength),
        });
        const image = images[images.length - 1];
        if (image.cameraIndex < 0 || image.width < 1 || image.height < 1 || image.colorChannels < 1) {
            throw new Error(`Invalid image dimensions or camera index for ${cameraId}`);
        }
        offset = jpegStart + jpegLength;
    }

    ensureBytes(offset, IMAGE_PAYLOAD_FOOTER_SIZE, "payload footer");
    if (view.getUint8(offset + IMAGE_PAYLOAD_FOOTER_FIELDS.message_type.offset) !== IMAGE_PAYLOAD_MESSAGE_TYPE.PAYLOAD_FOOTER
        || Number(view.getBigInt64(offset + IMAGE_PAYLOAD_FOOTER_FIELDS.frame_number.offset, true)) !== frameNumber
        || view.getInt32(offset + IMAGE_PAYLOAD_FOOTER_FIELDS.number_of_cameras.offset, true) !== cameraCount) {
        throw new Error("Image payload footer disagrees with its header");
    }
    offset += IMAGE_PAYLOAD_FOOTER_SIZE;
    if (offset !== bytes.byteLength) {
        throw new Error(`Image payload has ${bytes.byteLength - offset} trailing bytes`);
    }
    if (new Set(images.map(image => image.cameraId)).size !== images.length
        || new Set(images.map(image => image.cameraIndex)).size !== images.length) {
        throw new Error("Image payload repeats a camera ID or index");
    }
    return { frameNumber, images };
}

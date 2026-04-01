// binary-frame-parser.ts
import {
    MESSAGE_TYPE,
    PAYLOAD_HEADER_FIELDS,
    PAYLOAD_HEADER_SIZE,
    FRAME_HEADER_FIELDS,
    FRAME_HEADER_SIZE,
    PAYLOAD_FOOTER_FIELDS,
    PAYLOAD_FOOTER_SIZE,
} from './binary-protocol';

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    bitmap: ImageBitmap;
}

// Single reusable TextDecoder - created once, used forever
const sharedTextDecoder = new TextDecoder();

// Optimized ImageBitmap options for camera feeds
const BITMAP_OPTIONS: ImageBitmapOptions = {
    premultiplyAlpha: 'none',
    colorSpaceConversion: 'none',
    resizeQuality: 'pixelated'
};

/**
 * Parse an ASCII string field from the buffer (16-byte fixed-length camera_id)
 */
function parseAsciiField(view: DataView, baseOffset: number, fieldOffset: number, size: number): string {
    const offset = baseOffset + fieldOffset;

    // Find actual string length (until null terminator)
    let length = 0;
    while (length < size && view.getUint8(offset + length) !== 0) {
        length++;
    }

    if (length === 0) return '';

    const bytes = new Uint8Array(view.buffer, view.byteOffset + offset, length);
    return sharedTextDecoder.decode(bytes);
}

/**
 * Parse a multi-frame payload from binary data
 * Matches the Python create_frontend_payload function's output format
 */
export async function parseMultiFramePayload(
    data: ArrayBuffer
): Promise<ParsedFrame[] | null> {
    const view = new DataView(data);

    // Validate minimum size
    if (data.byteLength < PAYLOAD_HEADER_SIZE) {
        console.warn(`Payload too small: ${data.byteLength} bytes`);
        return null;
    }

    // Validate payload header
    const messageType = view.getUint8(PAYLOAD_HEADER_FIELDS.message_type.offset);
    if (messageType !== MESSAGE_TYPE.PAYLOAD_HEADER) {
        console.warn(`Invalid payload header: expected ${MESSAGE_TYPE.PAYLOAD_HEADER}, got ${messageType}`);
        return null;
    }

    // Extract payload header fields
    const frameNumber = Number(
        view.getBigInt64(PAYLOAD_HEADER_FIELDS.frame_number.offset, true)
    );

    const numCameras = view.getInt32(
        PAYLOAD_HEADER_FIELDS.number_of_cameras.offset,
        true
    );

    // Validate camera count
    if (numCameras <= 0 ) {
        console.warn(`Invalid camera count: ${numCameras}`);
        return null;
    }

    // Pre-allocate array for frame metadata
    const frameMetadata: Array<{
        cameraId: string;
        cameraIndex: number;
        frameNumber: number;
        width: number;
        height: number;
        colorChannels: number;
        jpegStart: number;
        jpegLength: number;
    }> = new Array(numCameras);

    let currentOffset = PAYLOAD_HEADER_SIZE;
    let validFrameCount = 0;

    // Parse each frame header
    for (let i = 0; i < numCameras; i++) {
        // Check if we have enough bytes for the frame header
        if (currentOffset + FRAME_HEADER_SIZE > data.byteLength) {
            console.warn(`Not enough bytes for frame header at offset ${currentOffset}`);
            break;
        }

        // Validate frame header message type
        const frameMessageType = view.getUint8(
            currentOffset + FRAME_HEADER_FIELDS.message_type.offset
        );

        if (frameMessageType !== MESSAGE_TYPE.FRAME_METADATA) {
            console.warn(
                `Invalid frame header at offset ${currentOffset}: ` +
                `expected ${MESSAGE_TYPE.FRAME_METADATA}, got ${frameMessageType}`
            );
            break;
        }

        // Extract frame number
        const frameNum = Number(
            view.getBigInt64(
                currentOffset + FRAME_HEADER_FIELDS.frame_number.offset,
                true
            )
        );

        // Extract camera_id (16-byte ASCII string)
        const cameraId = parseAsciiField(
            view,
            currentOffset,
            FRAME_HEADER_FIELDS.camera_id.offset,
            FRAME_HEADER_FIELDS.camera_id.size
        );

        // Extract camera_index
        const cameraIndex = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.camera_index.offset,
            true
        );

        // Extract image metadata
        const width = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.image_width.offset,
            true
        );

        const height = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.image_height.offset,
            true
        );

        const colorChannels = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.color_channels.offset,
            true
        );

        const jpegLength = view.getInt32(
            currentOffset + FRAME_HEADER_FIELDS.jpeg_string_length.offset,
            true
        );

        // Validate JPEG length
        if (jpegLength <= 0 ) {
            console.warn(`Invalid JPEG length: ${jpegLength}`);
            break;
        }

        // Check if we have enough bytes for the JPEG data
        const jpegStart = currentOffset + FRAME_HEADER_SIZE;
        if (jpegStart + jpegLength > data.byteLength) {
            console.warn(
                `Not enough bytes for JPEG data: need ${jpegLength} bytes ` +
                `at offset ${jpegStart}, but buffer only has ${data.byteLength} bytes`
            );
            break;
        }

        // Store metadata
        frameMetadata[validFrameCount] = {
            cameraId: cameraId,
            cameraIndex: cameraIndex,
            frameNumber: frameNum,
            width: width,
            height: height,
            colorChannels: colorChannels,
            jpegStart: jpegStart,
            jpegLength: jpegLength
        };

        validFrameCount++;
        currentOffset += FRAME_HEADER_SIZE + jpegLength;
    }

    if (validFrameCount === 0) {
        console.warn('No valid frames found in payload');
        return null;
    }

    // Optional: Validate footer if present
    if (currentOffset + PAYLOAD_FOOTER_SIZE <= data.byteLength) {
        const footerMessageType = view.getUint8(currentOffset + PAYLOAD_FOOTER_FIELDS.message_type.offset);
        if (footerMessageType === MESSAGE_TYPE.PAYLOAD_FOOTER) {
            const footerFrameNumber = Number(
                view.getBigInt64(currentOffset + PAYLOAD_FOOTER_FIELDS.frame_number.offset, true)
            );
            const footerNumCameras = view.getInt32(
                currentOffset + PAYLOAD_FOOTER_FIELDS.number_of_cameras.offset,
                true
            );

            if (footerFrameNumber !== frameNumber || footerNumCameras !== numCameras) {
                console.warn(
                    `Footer mismatch: header(frame=${frameNumber}, cameras=${numCameras}) ` +
                    `footer(frame=${footerFrameNumber}, cameras=${footerNumCameras})`
                );
            }
        }
    }

    // Trim array to actual size.
    frameMetadata.length = validFrameCount;

    // Create ImageBitmaps in parallel
    const bitmapPromises = frameMetadata.map(async (metadata) => {
        try {
            const jpegData = new Uint8Array(data, metadata.jpegStart, metadata.jpegLength);
            const blob = new Blob([jpegData], { type: 'image/jpeg' });
            const bitmap = await createImageBitmap(blob, BITMAP_OPTIONS);

            return {
                cameraId: metadata.cameraId,
                cameraIndex: metadata.cameraIndex,
                frameNumber: metadata.frameNumber,
                width: metadata.width,
                height: metadata.height,
                colorChannels: metadata.colorChannels,
                bitmap: bitmap,
            } as ParsedFrame;
        } catch (error) {
            console.error(`Failed to create bitmap for camera ${metadata.cameraId}:`, error);
            throw error;
        }
    });

    return Promise.all(bitmapPromises);
}

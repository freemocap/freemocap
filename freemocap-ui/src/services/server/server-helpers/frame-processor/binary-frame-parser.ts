// binary-frame-parser.ts
import {
    FRAME_HEADER_FIELDS,
    FRAME_HEADER_SIZE,
    MESSAGE_TYPE,
    PAYLOAD_FOOTER_FIELDS,
    PAYLOAD_FOOTER_SIZE,
    PAYLOAD_HEADER_FIELDS,
    PAYLOAD_HEADER_SIZE,
} from './binary-protocol';

// ---------------------------------------------------------------------------
// CPU JPEG decode (pure JS) — avoids GPU contention with the Three.js viewport.
//
// JPEG bytes are decoded via jpeg-js which runs entirely on the CPU. We return
// the raw RGBA pixel buffer — ImageBitmap creation is deferred to each
// per-camera worker so GPU uploads happen independently (not batched in a
// Promise.all that serializes on the GPU command queue).
//
// jpeg-js is pure JavaScript (no WASM), so it works in any Worker context
// without Vite WASM-loading issues.
// ---------------------------------------------------------------------------

// Lazily-resolved pure-JS decoder — loaded once on first use, cached forever.
let _cpuDecodePromise: Promise<
    (jpegData: Uint8Array) => { width: number; height: number; data: Uint8Array }
> | null = null;

function getCpuDecoder(): Promise<
    (jpegData: Uint8Array) => { width: number; height: number; data: Uint8Array }
> {
    if (!_cpuDecodePromise) {
        _cpuDecodePromise = import("jpeg-js").then((m) => {
            console.log("[binary-frame-parser] jpeg-js pure-JS decoder loaded (CPU path)");
            const decode = m.default.decode;
            // useTArray: true → returns Uint8Array instead of Node Buffer (browser compat)
            return (jpegData: Uint8Array) => decode(jpegData, { useTArray: true });
        });
    }
    return _cpuDecodePromise;
}

export interface ParsedFrame {
    cameraId: string;
    cameraIndex: number;
    frameNumber: number;
    width: number;
    height: number;
    colorChannels: number;
    pixelBuffer: ArrayBuffer;
}

// Single reusable TextDecoder - created once, used forever
const sharedTextDecoder = new TextDecoder();

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

    // Decode JPEG → raw RGBA pixel buffer for every camera in parallel.
    //
    // jpeg-js runs on CPU only — no GPU touch. Raw pixel buffers are returned
    // so that ImageBitmap creation (GPU upload) happens independently in each
    // per-camera worker, avoiding the GPU queue serialization that occurs when
    // 3 createImageBitmap calls race in a single Promise.all.
    const framePromises = frameMetadata.map(async (metadata) => {
        try {
            const decodeJpeg = await getCpuDecoder();
            const jpegData = new Uint8Array(data, metadata.jpegStart, metadata.jpegLength);
            const raw = decodeJpeg(jpegData); // synchronous

            // Slice the exact pixel buffer for zero-copy transfer to main thread.
            // raw.data is a Uint8Array from jpeg-js with useTArray:true.
            const pixelBuffer = raw.data.buffer.slice(
                raw.data.byteOffset,
                raw.data.byteOffset + raw.data.byteLength,
            );

            return {
                cameraId: metadata.cameraId,
                cameraIndex: metadata.cameraIndex,
                frameNumber: metadata.frameNumber,
                width: metadata.width,
                height: metadata.height,
                colorChannels: metadata.colorChannels,
                pixelBuffer,
            } as ParsedFrame;
        } catch (error) {
            console.error(`Failed to decode frame for camera ${metadata.cameraId}:`, error);
            throw error;
        }
    });

    return Promise.all(framePromises);
}

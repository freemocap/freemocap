// src/services/server/server-helpers/frame-processor/frame-decode.worker.ts
//
// Inline Web Worker that performs binary frame parsing and JPEG→ImageBitmap
// decoding off the main thread. All Blob allocations and createImageBitmap
// async work happen here, so their GC pressure never affects the UI.
//
// IMPORTANT: The binary protocol constants below are duplicated from
// binary-protocol.ts because Web Workers cannot use ES module imports or
// Vite path aliases. If the protocol changes, update BOTH files.

export const frameDecodeWorkerCode = `
// ─── Binary protocol constants (mirrored from binary-protocol.ts) ───

const MESSAGE_TYPE_PAYLOAD_HEADER = 0;
const MESSAGE_TYPE_FRAME_METADATA = 1;
const MESSAGE_TYPE_PAYLOAD_FOOTER = 2;

const PAYLOAD_HEADER_SIZE = 24;
const FRAME_HEADER_SIZE = 56;
const PAYLOAD_FOOTER_SIZE = 24;

// Payload header field offsets
const PH_MESSAGE_TYPE = 0;
const PH_FRAME_NUMBER = 8;
const PH_NUM_CAMERAS = 16;

// Frame header field offsets
const FH_MESSAGE_TYPE = 0;
const FH_FRAME_NUMBER = 8;
const FH_CAMERA_ID_OFFSET = 16;
const FH_CAMERA_ID_SIZE = 16;
const FH_CAMERA_INDEX = 32;
const FH_IMAGE_WIDTH = 36;
const FH_IMAGE_HEIGHT = 40;
const FH_COLOR_CHANNELS = 44;
const FH_JPEG_LENGTH = 48;

// Footer field offsets
const FT_MESSAGE_TYPE = 0;
const FT_FRAME_NUMBER = 8;
const FT_NUM_CAMERAS = 16;

const BITMAP_OPTIONS = {
    premultiplyAlpha: 'none',
    colorSpaceConversion: 'none',
    resizeQuality: 'pixelated',
};

const textDecoder = new TextDecoder();

// ─── Parsing helpers ───

function parseAsciiField(view, baseOffset, fieldOffset, size) {
    const offset = baseOffset + fieldOffset;
    let length = 0;
    while (length < size && view.getUint8(offset + length) !== 0) {
        length++;
    }
    if (length === 0) return '';
    const bytes = new Uint8Array(view.buffer, view.byteOffset + offset, length);
    return textDecoder.decode(bytes);
}

// ─── Main decode function ───

async function decodePayload(data) {
    const view = new DataView(data);

    if (data.byteLength < PAYLOAD_HEADER_SIZE) {
        throw new Error('Payload too small: ' + data.byteLength + ' bytes');
    }

    const messageType = view.getUint8(PH_MESSAGE_TYPE);
    if (messageType !== MESSAGE_TYPE_PAYLOAD_HEADER) {
        throw new Error('Invalid payload header: expected ' + MESSAGE_TYPE_PAYLOAD_HEADER + ', got ' + messageType);
    }

    const frameNumber = Number(view.getBigInt64(PH_FRAME_NUMBER, true));
    const numCameras = view.getInt32(PH_NUM_CAMERAS, true);

    if (numCameras <= 0) {
        throw new Error('Invalid camera count: ' + numCameras);
    }

    const frameMetadata = new Array(numCameras);
    let currentOffset = PAYLOAD_HEADER_SIZE;
    let validFrameCount = 0;

    for (let i = 0; i < numCameras; i++) {
        if (currentOffset + FRAME_HEADER_SIZE > data.byteLength) break;

        const fhType = view.getUint8(currentOffset + FH_MESSAGE_TYPE);
        if (fhType !== MESSAGE_TYPE_FRAME_METADATA) break;

        const frameNum = Number(view.getBigInt64(currentOffset + FH_FRAME_NUMBER, true));
        const cameraId = parseAsciiField(view, currentOffset, FH_CAMERA_ID_OFFSET, FH_CAMERA_ID_SIZE);
        const cameraIndex = view.getInt32(currentOffset + FH_CAMERA_INDEX, true);
        const width = view.getInt32(currentOffset + FH_IMAGE_WIDTH, true);
        const height = view.getInt32(currentOffset + FH_IMAGE_HEIGHT, true);
        const colorChannels = view.getInt32(currentOffset + FH_COLOR_CHANNELS, true);
        const jpegLength = view.getInt32(currentOffset + FH_JPEG_LENGTH, true);

        if (jpegLength <= 0) break;

        const jpegStart = currentOffset + FRAME_HEADER_SIZE;
        if (jpegStart + jpegLength > data.byteLength) break;

        frameMetadata[validFrameCount] = {
            cameraId,
            cameraIndex,
            frameNumber: frameNum,
            width,
            height,
            colorChannels,
            jpegStart,
            jpegLength,
        };

        validFrameCount++;
        currentOffset += FRAME_HEADER_SIZE + jpegLength;
    }

    if (validFrameCount === 0) {
        throw new Error('No valid frames found in payload');
    }

    // Optional footer validation
    if (currentOffset + PAYLOAD_FOOTER_SIZE <= data.byteLength) {
        const ftType = view.getUint8(currentOffset + FT_MESSAGE_TYPE);
        if (ftType === MESSAGE_TYPE_PAYLOAD_FOOTER) {
            const ftFrameNum = Number(view.getBigInt64(currentOffset + FT_FRAME_NUMBER, true));
            const ftNumCameras = view.getInt32(currentOffset + FT_NUM_CAMERAS, true);
            if (ftFrameNum !== frameNumber || ftNumCameras !== numCameras) {
                console.warn(
                    'Footer mismatch: header(frame=' + frameNumber + ', cameras=' + numCameras + ') ' +
                    'footer(frame=' + ftFrameNum + ', cameras=' + ftNumCameras + ')'
                );
            }
        }
    }

    frameMetadata.length = validFrameCount;

    // Decode JPEGs sequentially so only one Blob's backing store exists
    // at a time. Blob data lives in the browser's blob subsystem (outside
    // the V8 heap) and relies on Blink GC to free it. In a Worker with no
    // idle time, parallel Blob creation causes backing stores to accumulate
    // faster than GC can reclaim them, producing a slowly rising memory
    // floor. Sequential decode with explicit nulling keeps peak blob memory
    // at one JPEG instead of N, and gives the browser a clear release signal.
    const frames = new Array(validFrameCount);
    for (let i = 0; i < validFrameCount; i++) {
        const meta = frameMetadata[i];
        const jpegData = new Uint8Array(data, meta.jpegStart, meta.jpegLength);
        let blob = new Blob([jpegData], { type: 'image/jpeg' });
        const bitmap = await createImageBitmap(blob, BITMAP_OPTIONS);
        blob = null;
        frames[i] = {
            cameraId: meta.cameraId,
            cameraIndex: meta.cameraIndex,
            frameNumber: meta.frameNumber,
            width: meta.width,
            height: meta.height,
            colorChannels: meta.colorChannels,
            bitmap: bitmap,
        };
    }

    return frames;
}

// ─── Worker message handler ───

self.onmessage = async (e) => {
    const { type, payload, requestId } = e.data;

    if (type === 'decode') {
        try {
            const frames = await decodePayload(payload);

            // Build transferable list of all ImageBitmaps
            const transferList = frames.map((f) => f.bitmap);

            // Separate bitmaps from metadata for structured cloning
            const frameData = frames.map((f) => ({
                cameraId: f.cameraId,
                cameraIndex: f.cameraIndex,
                frameNumber: f.frameNumber,
                width: f.width,
                height: f.height,
                colorChannels: f.colorChannels,
            }));

            const bitmaps = frames.map((f) => f.bitmap);

            self.postMessage(
                { type: 'result', requestId, frameData, bitmaps },
                transferList
            );
        } catch (error) {
            self.postMessage({
                type: 'error',
                requestId,
                message: error instanceof Error ? error.message : String(error),
            });
        }
    }
};
`;

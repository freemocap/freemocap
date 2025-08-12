import {useCallback, useRef, useState} from "react";
import * as THREE from "three";

// Define the message types from the Python code
enum MessageType {
    PAYLOAD_HEADER = 0,
    FRAME_HEADER = 1,
    PAYLOAD_FOOTER = 2,
}

// Structure sizes and offsets based on the Python dtype definitions
// Payload Header constants
const PAYLOAD_HEADER_SIZE = 24;
const PAYLOAD_HEADER_MESSAGE_TYPE_OFFSET = 0;
const PAYLOAD_HEADER_MESSAGE_TYPE_SIZE = 1;
const PAYLOAD_HEADER_PADDING_SIZE = 7;
const PAYLOAD_HEADER_FRAME_NUMBER_OFFSET = PAYLOAD_HEADER_MESSAGE_TYPE_SIZE + PAYLOAD_HEADER_PADDING_SIZE;
const PAYLOAD_HEADER_FRAME_NUMBER_SIZE = 8;
const PAYLOAD_HEADER_NUM_CAMERAS_OFFSET = PAYLOAD_HEADER_FRAME_NUMBER_OFFSET + PAYLOAD_HEADER_FRAME_NUMBER_SIZE;
const PAYLOAD_HEADER_NUM_CAMERAS_SIZE = 4;
const PAYLOAD_HEADER_PADDING_END_SIZE = 4;

// Frame Header constants
const FRAME_HEADER_SIZE = 56;
const FRAME_HEADER_MESSAGE_TYPE_OFFSET = 0;
const FRAME_HEADER_MESSAGE_TYPE_SIZE = 1;
const FRAME_HEADER_PADDING_SIZE = 7;
const FRAME_HEADER_FRAME_NUMBER_OFFSET = FRAME_HEADER_MESSAGE_TYPE_SIZE + FRAME_HEADER_PADDING_SIZE;
const FRAME_HEADER_FRAME_NUMBER_SIZE = 8;
const FRAME_HEADER_CAMERA_ID_OFFSET = FRAME_HEADER_FRAME_NUMBER_OFFSET + FRAME_HEADER_FRAME_NUMBER_SIZE;
const FRAME_HEADER_CAMERA_ID_SIZE = 16;
const FRAME_HEADER_CAMERA_INDEX_OFFSET = FRAME_HEADER_CAMERA_ID_OFFSET + FRAME_HEADER_CAMERA_ID_SIZE;
const FRAME_HEADER_CAMERA_INDEX_SIZE = 4;
const FRAME_HEADER_IMAGE_WIDTH_OFFSET = FRAME_HEADER_CAMERA_INDEX_OFFSET + FRAME_HEADER_CAMERA_INDEX_SIZE;
const FRAME_HEADER_IMAGE_WIDTH_SIZE = 4;
const FRAME_HEADER_IMAGE_HEIGHT_OFFSET = FRAME_HEADER_IMAGE_WIDTH_OFFSET + FRAME_HEADER_IMAGE_WIDTH_SIZE;
const FRAME_HEADER_IMAGE_HEIGHT_SIZE = 4;
const FRAME_HEADER_COLOR_CHANNELS_OFFSET = FRAME_HEADER_IMAGE_HEIGHT_OFFSET + FRAME_HEADER_IMAGE_HEIGHT_SIZE;
const FRAME_HEADER_COLOR_CHANNELS_SIZE = 4;
const FRAME_HEADER_JPEG_LENGTH_OFFSET = FRAME_HEADER_COLOR_CHANNELS_OFFSET + FRAME_HEADER_COLOR_CHANNELS_SIZE;
const FRAME_HEADER_JPEG_LENGTH_SIZE = 4;

// Payload Footer constants
const PAYLOAD_FOOTER_SIZE = 24;
const PAYLOAD_FOOTER_MESSAGE_TYPE_OFFSET = 0;
const PAYLOAD_FOOTER_MESSAGE_TYPE_SIZE = 1;
const PAYLOAD_FOOTER_PADDING_SIZE = 7;
const PAYLOAD_FOOTER_FRAME_NUMBER_OFFSET = PAYLOAD_FOOTER_MESSAGE_TYPE_SIZE + PAYLOAD_FOOTER_PADDING_SIZE;
const PAYLOAD_FOOTER_FRAME_NUMBER_SIZE = 8;
const PAYLOAD_FOOTER_NUM_CAMERAS_OFFSET = PAYLOAD_FOOTER_FRAME_NUMBER_OFFSET + PAYLOAD_FOOTER_FRAME_NUMBER_SIZE;
const PAYLOAD_FOOTER_NUM_CAMERAS_SIZE = 4;
const PAYLOAD_FOOTER_PADDING_END_SIZE = 4;

interface MessageHeaderFooter {
    messageType: number;
    frameNumber: number;
    numberOfCameras: number;
}

interface FrameHeader {
    messageType: number;
    frameNumber: number;
    cameraId: string;
    cameraIndex: number;
    imageWidth: number;
    imageHeight: number;
    colorChannels: number;
    jpegStringLength: number;
}

export interface CameraImageData {
    imageBitmap?: ImageBitmap;
    imageWidth: number;
    imageHeight: number;
    frameNumber: number;
    cameraId: string;
    cameraIndex: number;
}

export interface CameraDisplaySize {
    width: number;
    height: number;
}

export interface FrameRenderAcknowledgment {
    frameNumber: number;
    displayImageSizes: Record<string, CameraDisplaySize>;
}
export const useWebsocketBinaryMessageProcessor = () => {
    const [latestCameraImageData, setLatestCameraImageData] = useState<Record<string, CameraImageData>>({});


    const textDecoderRef = useRef(new TextDecoder());


    const parsePayloadHeader = useCallback((dataView: DataView): MessageHeaderFooter | null => {
        try {
            const messageType = dataView.getUint8(PAYLOAD_HEADER_MESSAGE_TYPE_OFFSET);

            if (messageType !== MessageType.PAYLOAD_HEADER) {
                console.error(`Expected payload header (0), got ${messageType}`);
                return null;
            }

            const frameNumber = Number(dataView.getBigInt64(PAYLOAD_HEADER_FRAME_NUMBER_OFFSET, true));
            const numberOfCameras = dataView.getInt32(PAYLOAD_HEADER_NUM_CAMERAS_OFFSET, true);

            return {messageType, frameNumber, numberOfCameras};
        } catch (error) {
            console.error('Error parsing payload header:', error);
            return null;
        }
    }, []);

    const parseFrameHeader = useCallback((dataView: DataView, textDecoder: TextDecoder): FrameHeader | null => {
        try {
            const messageType = dataView.getUint8(FRAME_HEADER_MESSAGE_TYPE_OFFSET);

            if (messageType !== MessageType.FRAME_HEADER) {
                console.error(`Expected frame header (1), got ${messageType}`);
                return null;
            }

            const frameNumber = Number(dataView.getBigInt64(FRAME_HEADER_FRAME_NUMBER_OFFSET, true));

            // Extract camera ID (fixed 16 bytes)
            const cameraIdBytes = new Uint8Array(
                dataView.buffer,
                dataView.byteOffset + FRAME_HEADER_CAMERA_ID_OFFSET,
                FRAME_HEADER_CAMERA_ID_SIZE
            );

            // Find the null terminator
            let cameraIdLength = 0;
            while (cameraIdLength < FRAME_HEADER_CAMERA_ID_SIZE && cameraIdBytes[cameraIdLength] !== 0) {
                cameraIdLength++;
            }

            const cameraId = textDecoder.decode(cameraIdBytes.slice(0, cameraIdLength));
            const cameraIndex = dataView.getInt32(FRAME_HEADER_CAMERA_INDEX_OFFSET, true);
            const imageWidth = dataView.getInt32(FRAME_HEADER_IMAGE_WIDTH_OFFSET, true);
            const imageHeight = dataView.getInt32(FRAME_HEADER_IMAGE_HEIGHT_OFFSET, true);
            const colorChannels = dataView.getInt32(FRAME_HEADER_COLOR_CHANNELS_OFFSET, true);
            const jpegStringLength = dataView.getInt32(FRAME_HEADER_JPEG_LENGTH_OFFSET, true);


            return {
                messageType,
                frameNumber,
                cameraId,
                cameraIndex,
                imageWidth,
                imageHeight,
                colorChannels,
                jpegStringLength
            };
        } catch (error) {
            console.error('Error parsing frame header:', error);
            return null;
        }
    }, []);

    const parsePayloadFooter = useCallback((dataView: DataView,): MessageHeaderFooter | null => {
        try {
            const messageType = dataView.getUint8(PAYLOAD_FOOTER_MESSAGE_TYPE_OFFSET);

            if (messageType !== MessageType.PAYLOAD_FOOTER) {
                console.error(`Expected payload footer (2), got ${messageType}`);
                return null;
            }

            const frameNumber = Number(dataView.getBigInt64(PAYLOAD_FOOTER_FRAME_NUMBER_OFFSET, true));
            const numberOfCameras = dataView.getInt32(PAYLOAD_FOOTER_NUM_CAMERAS_OFFSET, true);

            return {messageType, frameNumber, numberOfCameras};
        } catch (error) {
            console.error('Error parsing payload footer:', error);
            return null;
        }
    }, []);


    const processBinaryMessage = useCallback(async (data: ArrayBuffer): Promise<FrameRenderAcknowledgment | null> => {
        try {
            let offset = 0;

            // Process payload header as a chunk
            const headerView = new DataView(data, offset, PAYLOAD_HEADER_SIZE);
            const payloadHeader = parsePayloadHeader(headerView);

            if (!payloadHeader) {
                return null;
            }

            const {frameNumber, numberOfCameras} = payloadHeader;
            offset += PAYLOAD_HEADER_SIZE;

            if (numberOfCameras <= 0) {
                console.warn(`No cameras found in frame ${frameNumber}`);
                return null;
            }
            const frameRenderAcknowledgment: FrameRenderAcknowledgment = {
                frameNumber: frameNumber,
                displayImageSizes: {},
            }

            // Process each camera frame
            const textDecoder = textDecoderRef.current;
            const newCameraImageData: Record<string, CameraImageData> = {};

            for (let i = 0; i < numberOfCameras; i++) {
                // Process frame header as a chunk
                const frameHeaderView = new DataView(data, offset, FRAME_HEADER_SIZE);
                const frameHeader = parseFrameHeader(frameHeaderView, textDecoder);

                if (!frameHeader) {
                    return null;
                }

                if (frameHeader.frameNumber !== frameNumber) {
                    console.error(`Frame header mismatch: expected frame ${frameNumber}, got ${frameHeader.frameNumber}`);
                    return null;
                }

                offset += FRAME_HEADER_SIZE;

                // Extract JPEG data as a chunk
                const jpegData = new Uint8Array(data, offset, frameHeader.jpegStringLength);
                offset += frameHeader.jpegStringLength;


                if (latestCameraImageData[frameHeader.cameraId]?.imageWidth !== frameHeader.imageWidth ||
                    latestCameraImageData[frameHeader.cameraId]?.imageHeight !== frameHeader.imageHeight) {
                    // If the image dimensions or frame number have changed, update the state
                    newCameraImageData[frameHeader.cameraId] =  {
                            imageWidth: frameHeader.imageWidth,
                            imageHeight: frameHeader.imageHeight,
                            frameNumber: frameHeader.frameNumber,
                            cameraId: frameHeader.cameraId,
                            cameraIndex: frameHeader.cameraIndex,
                            imageBitmap: await createImageBitmap(new Blob([jpegData], { type: 'image/jpeg' }))
                        }
                    }
                }
                setLatestCameraImageData(newCameraImageData);



            // Process payload footer as a chunk
            const footerView = new DataView(data, offset, PAYLOAD_FOOTER_SIZE);
            const payloadFooter = parsePayloadFooter(footerView);

            if (!payloadFooter) {
                return null;
            }

            // Verify footer matches header
            if (payloadFooter.frameNumber !== frameNumber || payloadFooter.numberOfCameras !== numberOfCameras) {
                console.error(`Footer mismatch: expected frame ${frameNumber}/${numberOfCameras}, got ${payloadFooter.frameNumber}/${payloadFooter.numberOfCameras}`);
                return null;
            }


            return frameRenderAcknowledgment;
        } catch (error) {
            console.error('Error processing binary frame:', error);
            return null;
        }
    }, [parsePayloadHeader, parseFrameHeader, parsePayloadFooter]);

    return {
        latestImageData: latestCameraImageData,
        processBinaryMessage,
    };
};

// skellycam-ui/src/store/thunks/camera-thunks.ts
import {createAsyncThunk} from '@reduxjs/toolkit';
import {setAvailableCameras, setCameraStatus, setError, setLoading} from "@/store/slices/cameras-slices/camerasSlice";
import {
    CAMERA_DEFAULT_CONSTRAINTS,
    CameraDevice,
    createDefaultCameraConfig
} from "@/store/slices/cameras-slices/camera-types";
import {RootState} from "@/store/AppStateStore";

const isVirtualCamera = (label: string): boolean => {
    const virtualCameraKeywords = ['virtual'];
    return virtualCameraKeywords.some(keyword => label.toLowerCase().includes(keyword));
};

export const validateVideoStream = async (deviceId: string): Promise<{ isValid: boolean; status: string }> => {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                deviceId: { exact: deviceId }
            }
        });

        const video = document.createElement('video');
        video.srcObject = stream;
        return new Promise((resolve) => {
            video.onloadedmetadata = () => {
                if (video.videoWidth > 0 && video.videoHeight > 0) {
                    resolve({ isValid: true, status: 'AVAILABLE' });
                } else {
                    resolve({ isValid: false, status: 'ERROR' });
                }
                stream.getTracks().forEach(track => track.stop());
                video.remove();
            };

            video.onerror = () => {
                stream.getTracks().forEach(track => track.stop());
                video.remove();
                resolve({ isValid: false, status: 'ERROR' });
            };

            setTimeout(() => {
                stream.getTracks().forEach(track => track.stop());
                video.remove();
                resolve({ isValid: false, status: 'ERROR' });
            }, 3000);
        });
    } catch (error) {
        console.warn(`Failed to validate device ${deviceId}:`, error);

        if (error instanceof DOMException) {
            if (error.name === 'NotReadableError' ||
                error.message.includes('in use') ||
                error.message.includes('busy') ||
                error.message.includes('already in use')) {
                return { isValid: false, status: 'IN_USE' };
            }
        }

        return { isValid: false, status: 'ERROR' };
    }
};

export const detectCameraDevices = createAsyncThunk(
    'cameras/detectBrowserDevices',
    async (filterVirtual: boolean = true, { dispatch, getState }) => {
        try {
            dispatch(setLoading(true));
            const devices = await navigator.mediaDevices.enumerateDevices();

            const cameras = devices.filter(({ kind }) => kind === "videoinput");
            if (cameras.length === 0) {
                dispatch(setError('No camera devices found'));
                console.warn('No camera devices found');
                return [];
            }
            console.log(`Found ${cameras.length} camera(s) `, cameras);

            const state = getState() as RootState;
            const existingCameras = state.cameras.cameras;

            const initialFiltered = filterVirtual ?
                cameras.filter(({ label }) => !isVirtualCamera(label)) :
                cameras;
            console.log(`After removing virtual cameras, ${initialFiltered.length} camera(s) remain`, initialFiltered);

            Object.keys(existingCameras).forEach(cameraId => {
                const stillExists = initialFiltered.some(device => device.deviceId.slice(-5) === cameraId);
                if (!stillExists) {
                    dispatch(setCameraStatus({ cameraId, status: 'UNAVAILABLE' }));
                }
            });

            const validatedCameras: CameraDevice[] = [];
            for (const camera of initialFiltered) {
                const cameraId = camera.deviceId.slice(-5);
                const validationResult = await validateVideoStream(camera.deviceId);
                    const existingCamera = existingCameras[cameraId];
                    const newCamera: CameraDevice = {
                        ...camera.toJSON(),
                        index: existingCamera?.index ?? validatedCameras.length,
                        cameraId,
                    selected: existingCamera?.selected ?? (validationResult.status === 'AVAILABLE'),
                    status: validationResult.status,
                constraints: CAMERA_DEFAULT_CONSTRAINTS,
                        config: existingCamera?.config ||
                            createDefaultCameraConfig(
                                existingCamera?.index ?? validatedCameras.length,
                                camera.label,
                                cameraId
                            )
                    };

                    validatedCameras.push(newCamera);
                if (!validationResult.isValid) {
                    console.warn(`Camera ${camera.label} validation status: ${validationResult.status}`);
                }
            }
            console.log(`After validation, ${validatedCameras.length} camera(s) processed`, validatedCameras);

            dispatch(setAvailableCameras(validatedCameras));
            dispatch(setError(null));
            return validatedCameras;
        } catch (error) {
            dispatch(setError('Failed to detect browser devices'));
            console.error('Error detecting browser devices:', error);
        } finally {
            dispatch(setLoading(false));
        }
    }
);

import {CharucoObservation, CharucoOverlayDataMessage} from "@/services/server/server-helpers/image-overlay/charuco-types";
import {MediapipeObservation, MediapipeOverlayDataMessage} from "@/services/server/server-helpers/image-overlay/mediapipe-types";

// Union type for all observation data messages
export type ObservationDataMessage = CharucoOverlayDataMessage | MediapipeOverlayDataMessage;

// Union type for individual observations
export type Observation = CharucoObservation | MediapipeObservation;

// Type guard functions
export function isCharucoObservation(obs: Observation): obs is CharucoObservation {
    return obs.message_type === 'charuco_overlay';
}

export function isMediapipeObservation(obs: Observation): obs is MediapipeObservation {
    return obs.message_type === 'mediapipe_overlay';
}

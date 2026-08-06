import type {TFunction} from 'i18next';

const STAGE_TOOLTIPS: Record<string, {short: string; long: string}> = {
    // ── Tracker timer stages ──
    'skeleton_inference:frame_read': {
        short: 'Frame read',
        long: 'Time to read camera images from the shared memory ring buffer before inference.',
    },
    'skeleton_inference:predict_batch': {
        short: 'Batch inference',
        long: 'Total wall-clock time for one batched ONNX inference pass across all cameras.',
    },
    'skeleton_inference:predict_per_camera': {
        short: 'Per-camera inference',
        long: 'Average inference time per camera (batch inference time divided by camera count).',
    },
    'skeleton_inference:dropped_frames': {
        short: 'Dropped frames',
        long: 'Number of frames skipped because the inference node fell behind the camera frame rate.',
    },

    // ── Skellytracker fine-grained stages ──
    'skeleton_inference:object_detection': {
        short: 'Object detection',
        long: 'Batched human-detection inference that locates people in the camera frames.',
    },
    'skeleton_inference:object_detection_infer': {
        short: 'Object detection infer',
        long: 'Raw ONNX inference time for the human-detection model across all batched camera images.',
    },
    'skeleton_inference:keypoint_detection': {
        short: 'Keypoint postprocess',
        long: 'Postprocess raw heatmaps into keypoint coordinates, translate keypoints back to full-image coordinates.',
    },
    'skeleton_inference:keypoint_detection_infer': {
        short: 'Keypoint detection infer',
        long: 'Raw ONNX inference time for the pose-estimation model across all batched camera images.',
    },
    'skeleton_inference:bbox_reuse': {
        short: 'BBox reuse',
        long: 'Time saved by reusing the previous frame bounding box instead of running full detection.',
    },
    'skeleton_inference:bbox_smoothing': {
        short: 'BBox smoothing',
        long: 'Temporal smoothing applied to bounding boxes to reduce jitter between frames.',
    },
    'skeleton_inference:crop': {
        short: 'Crop',
        long: 'Time to crop detected human regions from the raw camera image before keypoint detection.',
    },
    'skeleton_inference:keypoint_smoothing': {
        short: 'Keypoint smoothing',
        long: 'Temporal smoothing applied to 2D keypoints to reduce jitter between frames.',
    },
    'skeleton_inference:keypoint_merge': {
        short: 'Keypoint merge',
        long: 'Time to merge keypoint detections from multiple model outputs into a unified result.',
    },
    'skeleton_inference:keypoint_tracked_bbox': {
        short: 'Tracked BBox',
        long: 'Time to compute a tracked bounding box from the detected keypoints for the next frame.',
    },

    // ── Legacy RTMPose stages (synthesize fallback) ──
    'skeleton_inference:human_detection_letterbox': {
        short: 'Letterbox',
        long: 'Resizing the camera image to fit the model input dimensions while preserving aspect ratio.',
    },
    'skeleton_inference:human_detection_batch_pack': {
        short: 'Batch pack',
        long: 'Packing multiple camera images into a single tensor batch for the detection model.',
    },
    'skeleton_inference:human_detection_preprocess': {
        short: 'Detection preprocess',
        long: 'Combined preprocessing steps (letterbox and batch packing) before the human detection model runs.',
    },
    'skeleton_inference:human_detection': {
        short: 'Human detection',
        long: 'Running the ONNX human-detection model to locate people in the camera frames.',
    },
    'skeleton_inference:human_detection_postprocess': {
        short: 'Detection postprocess',
        long: 'Postprocessing the detection model raw output into usable bounding boxes.',
    },
    'skeleton_inference:pose_estimation_preprocess': {
        short: 'Pose preprocess',
        long: 'Preparing detected human regions for the pose estimation model input.',
    },
    'skeleton_inference:pose_estimation': {
        short: 'Pose estimation',
        long: 'Running the ONNX pose-estimation model to predict body keypoint coordinates.',
    },
    'skeleton_inference:pose_estimation_postprocess': {
        short: 'Pose postprocess',
        long: 'Postprocessing the pose model raw heatmaps into 2D keypoint coordinates.',
    },

    // ── Multiframe ──
    'multiframe:ws_payload_prepare_ms': {
        short: 'WS payload prepare',
        long: 'Time to serialize and prepare the WebSocket payload for one multiframe.',
    },
};

export function getPipelineStageRowTooltip(
    rowKey: string,
    _t: TFunction,
): {short: string; long: string} {
    // Try exact match first
    const entry = STAGE_TOOLTIPS[rowKey];
    if (entry) {
        return entry;
    }
    // Normalize nodeKind:cameraId:stage → nodeKind:stage
    const parts = rowKey.split(':');
    if (parts.length >= 3) {
        const normalized = `${parts[0]}:${parts.slice(2).join(':')}`;
        const normalizedEntry = STAGE_TOOLTIPS[normalized];
        if (normalizedEntry) {
            return normalizedEntry;
        }
    }
    return {
        short: rowKey.replace(/^.*:/, ''),
        long: 'No description available for this metric.',
    };
}

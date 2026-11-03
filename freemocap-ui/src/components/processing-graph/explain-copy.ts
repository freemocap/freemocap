// Text for the explain view's callouts about stages, their data and their saved files. Settings explain
// themselves with the same text as their info buttons.
import type {DataKey, NodeId} from './stage-graph';

export const STAGE_TEXT: Record<NodeId, string> = {
    recording: 'The recording folder: its synchronized videos and the calibration the cameras were calibrated with.',
    observations: 'Detects the skeleton keypoints in every frame of every video, with the selected detector.',
    triangulation: 'Matches the cameras\' 2D keypoints and calculates each keypoint\'s 3D position.',
    filtering: 'Fills short gaps in the 3D trajectories and smooths them with a low-pass filter.',
    scale_fit: 'Fits this person\'s body segment lengths to the filtered 3D keypoints.',
    reconstruction: 'Fits the skeleton to every frame, giving each rigid-body segment its position and rotation.',
    blender: 'Builds a Blender scene from the reconstructed skeleton after processing.',
    exports: 'Writes the selected data as files after processing. Everything is always saved in the recording\'s Parquet file.',
};

export const DATA_TEXT: Record<DataKey, string> = {
    calibration: 'Camera intrinsics and poses from the recording\'s calibration file.',
    videos: 'The recording\'s synchronized videos, one per camera.',
    keypoints2d: 'Keypoints detected in each video, per camera and frame.',
    annotated: 'Copies of the videos with the detected keypoints drawn on them.',
    raw3d: 'Triangulated 3D positions before gap filling.',
    filtered3d: '3D positions with gaps filled and noise smoothed.',
    dimensions: 'The fitted length of each body segment.',
    segments: 'Each rigid-body segment\'s position and world rotation, per frame.',
    landmarks: 'Anatomical landmark positions on the fitted skeleton, per frame.',
    blend: 'A .blend file of the animated skeleton.',
    files: 'The export files in the selected formats.',
};

export const SAVE_TEXT = 'Where this stage writes its results. Click a file to open its folder.';

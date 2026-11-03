import {useMemo} from 'react';
import {useAppSelector} from '@/store/hooks';
import {RTMPOSE_MODELS, selectMocapRecordingPath} from '@/store/slices/mocap';
import {selectBlender, selectBlenderExePath} from '@/store/slices/blender';
import {EXECUTION_PROVIDERS} from '@/types/execution-provider';
import {DETECTOR_OPTIONS} from '@/components/mocap-setup/detector-options';
import type {ExportFormat} from '@/types/recording-exports';
import {basename} from './graph-model';
import type {SectionSettings} from './section-graph';

const FORMAT_NAMES: Record<ExportFormat, string> = {wide_csv: 'Wide CSV', npz: 'NPZ', npy: 'NPY', notebook: 'Notebook'};
const MEDIAPIPE_SIZES: Record<string, string> = {heavy: 'Heavy', full: 'Full', lite: 'Lite'};
const ALIGNMENT: Record<string, string> = {auto: 'Automatic', calibration: 'Use calibration', person: 'Align to person'};

/** The Mocap panel's current settings, labelled as the panel labels them, for the graph's section cards. */
export function useSectionSettings(): SectionSettings {
    const path = useAppSelector(selectMocapRecordingPath);
    const calibration = useAppSelector(state => state.calibration.loadedCalibration);
    const config = useAppSelector(state => state.mocap.config);
    const blender = useAppSelector(selectBlender);
    const blenderExe = useAppSelector(selectBlenderExePath);
    return useMemo((): SectionSettings => {
        const detector = DETECTOR_OPTIONS.find(option => option.value === config.detectorType);
        if (!detector) throw new Error(`Unknown detector "${config.detectorType}"`);
        const provider = EXECUTION_PROVIDERS.find(option => option.value === config.executionProvider)?.label ?? `${config.executionProvider}`;
        const rtmw = [
            {label: 'Model', value: RTMPOSE_MODELS.find(model => model.value === config.rtmPoseModelName)?.label ?? config.rtmPoseModelName},
            {label: 'Confidence threshold', value: `${config.rtmPoseConfidenceThreshold}`},
            {label: 'Execution provider', value: provider},
        ];
        const mediapipe = [
            {label: 'Pose model size', value: MEDIAPIPE_SIZES[config.mediapipeModelComplexity] ?? config.mediapipeModelComplexity},
            {label: 'Detection confidence', value: `${config.mediapipeDetectionConfidence}`},
        ];
        const detectorRows = config.detectorType === 'rtmpose' ? rtmw
            : config.detectorType === 'rtmw_mediapipe_hands' ? [...rtmw, mediapipe[1]]
                : config.detectorType === 'mediapipe' ? mediapipe
                    : [{label: 'Confidence threshold', value: `${config.dlcConfidenceThreshold}`}];
        return {
            recordingName: path ? basename(path) : '',
            calibrationFile: calibration ? basename(calibration.path) : null,
            detector: detector.label, detectorRows, charuco: config.charucoTrackingEnabled,
            alignment: ALIGNMENT[config.bodyAlignmentMode] ?? config.bodyAlignmentMode,
            customTransform: config.referenceTransformEnabled && config.bodyAlignmentMode !== 'calibration',
            triangulation: {outlierRejection: config.triangulation.use_outlier_rejection, minimumCameras: config.triangulation.minimum_cameras_for_triangulation,
                maximumDropped: config.triangulation.maximum_cameras_to_drop, targetError: config.triangulation.target_reprojection_error},
            filter: {enabled: config.posthoc_filter.enabled, cutoff: config.posthoc_filter.cutoff, order: config.posthoc_filter.order},
            blender: {executableFound: Boolean(blenderExe), exportAfter: blender.exportToBlenderEnabled, openWhenDone: blender.autoOpenBlendFile,
                formats: blender.exportConfig.formats.map(format => format.toUpperCase())},
            exports: {formats: config.exportFormats.map(format => FORMAT_NAMES[format]), exportAfter: config.exportAfterProcessing,
                tallCsv: config.exportTallCsv, channels: config.exportChannels},
        };
    }, [path, calibration, config, blender, blenderExe]);
}

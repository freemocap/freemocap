// The Mocap processing window's sections, in pipeline order. The outline, the list view and the graph
// view all draw these, so a stage has one name, one switch and one set of settings everywhere.
import type {ReactNode} from 'react';
import {useAppSelector} from '@/store/hooks';
import {RTMPOSE_MODELS} from '@/store/slices/mocap';
import {selectSourceRunId} from '@/store/slices/processing-stages';
import {selectBlender} from '@/store/slices/blender';
import {useMocap} from '@/hooks/useMocap';
import type {ResumeStage} from '@/services/recording/posthoc-processing';
import type {ExportFormat} from '@/types/recording-exports';
import SettingsSummaryChip from '@/components/common/settings-layout/settings-summary-chip';
import ProcessingDirectorySettings from './mocap-processing-directory';
import CaptureVolumeSettings from './capture-volume-settings';
import CameraGeometrySummary from './camera-geometry-summary';
import MocapDetectorSettings from './mocap-detector-settings';
import TriangulationSettings from './mocap-triangulation-settings';
import ReferenceFrameSettings from './reference-frame-settings';
import PosthocFilterSettings from './mocap-postprocess-settings';
import ScaleFitSettings from './scale-fit-settings';
import MocapExportSettings from './mocap-export-settings';
import MocapBlenderSettings from './mocap-blender-settings';
import {BlenderMissingNotice} from './processing-run-controls';
import {STAGE_TITLES} from './stage-titles';

const FORMAT_SHORT_NAMES: Record<ExportFormat, string> = {wide_csv: 'Wide CSV', npz: 'NPZ', npy: 'NPY', notebook: 'Notebook'};

export type SectionId = 'recording' | ResumeStage | 'blender' | 'exports';

export interface ProcessingSection {
    id: SectionId;
    /** The processing stage number shown beside the title, for stages. */
    number: number | null;
    title: string;
    /** The stage this section runs, or null for the recording and the after-processing outputs. */
    stage: ResumeStage | null;
    /** Short state chips for the section header. */
    summary: ReactNode;
    /** The section's settings; null when the stage has none. */
    content: ReactNode | null;
}


export function useProcessingSections(mode: 'recording' | 'playback'): ProcessingSection[] {
    const config = useAppSelector(state => state.mocap.config);
    const blender = useAppSelector(selectBlender);
    const sourceRunId = useAppSelector(selectSourceRunId);
    const {mocapRecordingPath, isLoading, isRecording} = useMocap();
    const recordingName = mocapRecordingPath?.split(/[\\/]/).filter(Boolean).pop() ?? '';
    const model = RTMPOSE_MODELS.find(entry => entry.value === config.rtmPoseModelName);
    const detector = config.detectorType === 'dlc' ? 'DLC'
        : config.detectorType === 'mediapipe' ? `MediaPipe · ${config.mediapipeModelComplexity}`
            : [config.detectorType === 'rtmw_mediapipe_hands' ? 'RTMW + MediaPipe hands' : 'RTMW', model?.label].filter(Boolean).join(' · ');
    const stage = (id: ResumeStage, number: number, summary: ReactNode, content: ReactNode | null): ProcessingSection =>
        ({id, number, title: STAGE_TITLES[id], stage: id, summary, content});
    return [
        {id: 'recording', number: null, title: 'Recording', stage: null,
            summary: <>
                {recordingName && <SettingsSummaryChip tone="path" title={mocapRecordingPath ?? ''}>{recordingName}</SettingsSummaryChip>}
                <CameraGeometrySummary mode={mode}/>
            </>,
            content: <>
                <ProcessingDirectorySettings open onClose={() => {}}/>
                <CaptureVolumeSettings mode={mode}/>
            </>},
        stage('observations', 1, <>
            <SettingsSummaryChip>{detector}</SettingsSummaryChip>
            <SettingsSummaryChip tone="quiet">{config.charucoTrackingEnabled ? '+ Charuco' : ''}</SettingsSummaryChip>
        </>, <MocapDetectorSettings/>),
        stage('triangulation', 2, <SettingsSummaryChip>
            {config.triangulation.use_outlier_rejection ? `outlier rejection · ≥${config.triangulation.minimum_cameras_for_triangulation} cams` : ''}
        </SettingsSummaryChip>, <>
            <TriangulationSettings/>
            {mode === 'playback' && <ReferenceFrameSettings/>}
        </>),
        stage('filtering', 3, <SettingsSummaryChip>
            {config.posthoc_filter.enabled ? `Butterworth · ${config.posthoc_filter.cutoff} Hz · order ${config.posthoc_filter.order}` : 'Filtering off'}
        </SettingsSummaryChip>, <PosthocFilterSettings/>),
        stage('scale_fit', 4, <SettingsSummaryChip>{`anchor · ${config.anchorSegmentName}`}</SettingsSummaryChip>, <ScaleFitSettings/>),
        stage('reconstruction', 5, null, null),
        {id: 'blender', number: null, title: 'Blender', stage: null,
            summary: <SettingsSummaryChip tone="quiet">{blender.exportConfig.formats.map(format => format.toUpperCase()).join(' · ')}</SettingsSummaryChip>,
            content: <>
                <BlenderMissingNotice/>
                <MocapBlenderSettings/>
            </>},
        {id: 'exports', number: null, title: 'Exports', stage: null,
            summary: <SettingsSummaryChip>{config.exportFormats.length ? config.exportFormats.map(format => FORMAT_SHORT_NAMES[format]).join(' · ') : 'Parquet only'}{config.exportTallCsv ? ' · Tall CSV' : ''}</SettingsSummaryChip>,
            content: <MocapExportSettings sourceRunId={sourceRunId} key={mocapRecordingPath} path={mocapRecordingPath} processing={isLoading || isRecording}/>},
    ];
}

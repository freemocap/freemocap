import {useState} from 'react';
import {Matrix4} from 'three';
import ButtonSm from '@/components/ui-components/ButtonSm';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import TransformEditor from '@/components/mocap-setup/transform-editor';
import ReferenceTransformSummary from '@/components/mocap-setup/reference-transform-summary';
import {transformFields, transformFromFields, TransformRepresentation} from '@/components/mocap-setup/reference-transform';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {useAppDispatch, useAppSelector} from '@/store';
import {pipelineConfigUpdated} from '@/store/slices/realtime';
import {saveCalibrationTransform} from '@/store/slices/calibration/calibration-save';

export default function CalibrationReferenceFrame({calibrationPath}: {calibrationPath: string | null}) {
    const [editing, setEditing] = useState(false);
    const dispatch = useAppDispatch();
    const {pipelineConfig, aggregatorConfig, applyOrUpdatePipelineConfig, error, isLoading} = useRealtimePipelineSync();
    const calibration = useAppSelector(state => state.calibration);
    const busy = isLoading || calibration.isSaving || calibration.isLoading
        || calibration.isRecording || Boolean(calibration.loadRequestId);
    const offset = aggregatorConfig.reference_transform;
    const apply = (matrix: Matrix4 | null): void => {
        if (busy) return;
        const config = {...pipelineConfig, aggregator_config: {
            ...aggregatorConfig,
            calibration_toml_path: calibrationPath ?? aggregatorConfig.calibration_toml_path,
            reference_transform: matrix ? {matrix: transformFields(matrix, TransformRepresentation.Matrix)} : null,
        }};
        dispatch(pipelineConfigUpdated(config));
        applyOrUpdatePipelineConfig(config);
        setEditing(false);
    };
    return <div className="flex flex-col gap-1 p-1" aria-label="Streaming calibration reference frame">
        <div className="flex flex-row items-center gap-1">
            <ButtonSm text="Reference frame…" buttonType="secondary" iconClass="settings-icon" className="streaming-reference-button" disabled={busy} onClick={() => setEditing(true)}/>
            <AnchoredInfo title="Streaming reference frame" text={<>
                <p>Apply a fixed rotation and translation to the selected calibration's live camera geometry and multicamera reconstruction.</p>
                <p>X right, Y forward, Z up; translation in millimeters. Each accepted transform replaces the offset from the calibration frame.</p>
                <p>Edits apply at runtime. “Apply to calibration file” saves the current offset into the selected file, records it in history, and resets the runtime offset after saving.</p>
            </>}/>
            {offset && <ButtonSm text="Reset frame" buttonType="secondary" className="streaming-reference-button" disabled={busy} onClick={() => apply(null)}/>}
        </div>
        <ButtonSm
            text={calibration.isSaving ? 'Saving…' : 'Apply to calibration file'}
            buttonType="secondary"
            title={calibration.loadedCalibration?.path}
            disabled={busy || editing || !offset || !calibration.loadedCalibration
                || calibration.loadedCalibration.path !== calibrationPath
                || aggregatorConfig.calibration_toml_path !== calibrationPath}
            onClick={() => {void dispatch(saveCalibrationTransform());}}
        />
        {offset && <span className="text sm text-gray" role="status">Custom reference offset</span>}
        {offset && <ReferenceTransformSummary
            matrix={transformFromFields(offset.matrix, TransformRepresentation.Matrix)}
            label="Runtime transformation"/>}
        {error && <p role="alert" className="text-error">{error}</p>}
        {calibration.error && <p role="alert" className="text-error">{calibration.error}</p>}
        {editing && <TransformEditor
            initialMatrix={offset ? transformFromFields(offset.matrix, TransformRepresentation.Matrix) : new Matrix4()}
            onAccept={apply} onClose={() => setEditing(false)}/>}
    </div>;
}

import {useState} from 'react';
import {Matrix4} from 'three';
import ButtonSm from '@/components/ui-components/ButtonSm';
import AnchoredInfo from '@/components/ui-components/AnchoredInfo';
import TransformEditor from '@/components/mocap-setup/transform-editor';
import {transformFields, transformFromFields, TransformRepresentation} from '@/components/mocap-setup/reference-transform';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {useAppDispatch} from '@/store';
import {pipelineConfigUpdated} from '@/store/slices/realtime';

export default function CalibrationReferenceFrame({calibrationPath}: {calibrationPath: string | null}) {
    const [editing, setEditing] = useState(false);
    const dispatch = useAppDispatch();
    const {pipelineConfig, aggregatorConfig, applyOrUpdatePipelineConfig, error} = useRealtimePipelineSync();
    const offset = aggregatorConfig.reference_transform;
    const apply = (matrix: Matrix4 | null): void => {
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
            <ButtonSm text="Reference frame…" buttonType="secondary" iconClass="settings-icon" className="streaming-reference-button" onClick={() => setEditing(true)}/>
            <AnchoredInfo title="Streaming reference frame" text={<>
                <p>Apply a fixed rotation and translation to the selected calibration's live camera geometry and multicamera reconstruction.</p>
                <p>X right, Y forward, Z up; translation in millimeters. Each accepted transform replaces the offset from the calibration frame.</p>
                <p>The calibration file is unchanged. Posthoc processing has its own reference-frame setting.</p>
            </>}/>
            {offset && <ButtonSm text="Reset frame" buttonType="secondary" className="streaming-reference-button" onClick={() => apply(null)}/>}
        </div>
        {offset && <span className="text sm text-gray" role="status">Custom reference offset</span>}
        {error && <p role="alert" className="text-error">{error}</p>}
        {editing && <TransformEditor
            initialMatrix={offset ? transformFromFields(offset.matrix, TransformRepresentation.Matrix) : new Matrix4()}
            onAccept={apply} onClose={() => setEditing(false)}/>}
    </div>;
}

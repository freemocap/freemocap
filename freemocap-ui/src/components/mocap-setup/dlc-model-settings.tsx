import {useEffect, useRef, useState} from 'react';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {mocapDlcSettingsChanged} from '@/store/slices/mocap';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {getDlcReadiness, inspectDlcModel, importDlcModel, getDlcImportJob,
    type DlcModelMetadata, type DlcReadiness, type DlcImportJob} from '@/services/server/dlc-models';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import ValueSelector from '@/components/ui-components/ValueSelector';

/** One model-selection surface for all detector menus; Tracker owns model interpretation. */
export function DlcModelSettings({context}: {context: 'realtime' | 'posthoc'}) {
    const dispatch = useAppDispatch();
    const saved = useAppSelector(state => state.mocap.config);
    const {pipelineConfig, cameraNodeConfig, applyOrUpdatePipelineConfig, triggerRealtimeApply} = useRealtimePipelineSync();
    const selectedPath = context === 'realtime' ? cameraNodeConfig.dlc_model_path : saved.dlcModelPath;
    const confidence = context === 'realtime' ? cameraNodeConfig.dlc_confidence_threshold ?? 0.4 : saved.dlcConfidenceThreshold;
    const [modelPath, setModelPath] = useState(selectedPath ?? saved.dlcModelPath ?? '');
    const [metadata, setMetadata] = useState<DlcModelMetadata | null>(null);
    const [readiness, setReadiness] = useState<DlcReadiness | null>(null);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [job, setJob] = useState<DlcImportJob | null>(null);
    const [poseConfig, setPoseConfig] = useState('');
    const [checkpoint, setCheckpoint] = useState('');
    const [projectConfig, setProjectConfig] = useState('');
    const [imageWidth, setImageWidth] = useState(640);
    const [imageHeight, setImageHeight] = useState(480);
    const lifetime = useRef<AbortController | null>(null);
    useEffect(() => {
        const controller = new AbortController();
        lifetime.current = controller;
        getDlcReadiness(controller.signal).then(setReadiness).catch(reason => {
            if (!controller.signal.aborted) setError(String(reason.message ?? reason));
        });
        return () => controller.abort();
    }, []);
    useEffect(() => {
        setModelPath(selectedPath ?? saved.dlcModelPath ?? '');
        setMetadata(null);
        if (!selectedPath) return;
        const controller = new AbortController();
        inspectDlcModel(selectedPath, controller.signal).then(setMetadata).catch(reason => {
            if (!controller.signal.aborted) setError(String(reason.message ?? reason));
        });
        return () => controller.abort();
    }, [selectedPath, saved.dlcModelPath]);
    const selectModel = (model: DlcModelMetadata) => {
        setMetadata(model);
        setModelPath(model.sidecar_path);
        dispatch(mocapDlcSettingsChanged({dlcModelPath: model.sidecar_path}));
        if (context === 'realtime') applyOrUpdatePipelineConfig({...pipelineConfig,
            camera_node_config: {...cameraNodeConfig, dlc_model_path: model.sidecar_path}});
    };
    const selectModelRef = useRef(selectModel);
    selectModelRef.current = selectModel;
    useEffect(() => {
        if (!job || !['queued', 'running'].includes(job.status)) return;
        const controller = new AbortController();
        const timer = setTimeout(() => {
            getDlcImportJob(job.job_id, controller.signal).then(result => {
                setJob(result);
                if (result.status === 'complete' && result.result) {
                    selectModelRef.current(result.result);
                    setBusy(false);
                } else if (result.status === 'failed') {
                    setError(result.detail);
                    setBusy(false);
                }
            }).catch(reason => {
                if (!controller.signal.aborted) {setError(String(reason.message ?? reason)); setBusy(false);}
            });
        }, 1000);
        return () => {clearTimeout(timer); controller.abort();};
    }, [job]);
    const perform = async (action: () => Promise<void>) => {
        setBusy(true); setError('');
        try {await action();} catch (reason) {
            if (!lifetime.current?.signal.aborted) setError(reason instanceof Error ? reason.message : String(reason));
        } finally {if (!lifetime.current?.signal.aborted) setBusy(false);}
    };
    return <div className="flex flex-col gap-2 p-2 bg-middark br-1" style={{maxWidth: 520}}>
        <p className="text-sm">DLC tracks this model’s named keypoints in 2D. Calibration, anatomical reconstruction and Blender export are not used.</p>
        <label className="flex flex-col gap-1 text-sm">Converted model sidecar path
            <input className="input" value={modelPath} onChange={event => setModelPath(event.target.value)} placeholder="Path on the server to model.yaml"/>
        </label>
        <button className="button sm secondary" disabled={busy || !modelPath.trim()} onClick={() => void perform(async () => {
            selectModel(await inspectDlcModel(modelPath.trim(), lifetime.current?.signal));
        })}>Inspect and select model</button>
        {metadata && <div className="text-sm" style={{overflowWrap: 'anywhere'}}>
            <p>{metadata.keypoint_names.length} keypoints · {metadata.input_size[1]} × {metadata.input_size[0]} · {metadata.resize_method}</p>
            <p>{metadata.keypoint_names.join(', ')}</p>
            <p>{metadata.connections.length} keypoint connections</p>
        </div>}
        <SettingRow info={{title: "DLC execution provider", text: "Explicit ONNX CPU or CUDA execution in FP32. Session startup verifies availability; no automatic fallback."}} label="DLC execution provider" control={<SettingSelectInput label="DLC execution provider"
            value={saved.dlcExecutionProvider ?? 'cpu'} options={[{label: 'CPU · FP32', value: 'cpu'}, {label: 'CUDA · FP32', value: 'cuda'}]}
            onChange={(value: 'cpu' | 'cuda') => {dispatch(mocapDlcSettingsChanged({dlcExecutionProvider: value})); if (context === 'realtime') triggerRealtimeApply();}}/>}/>
        <SettingRow info={{title: "Keypoint confidence", text: "Suppress model keypoints below this confidence threshold."}} label="Keypoint confidence" control={<ValueSelector value={confidence} min={0} max={1} step={0.05} unit=""
            onChange={value => {
                if (context === 'posthoc') dispatch(mocapDlcSettingsChanged({dlcConfidenceThreshold: value}));
                else applyOrUpdatePipelineConfig({...pipelineConfig, camera_node_config: {...cameraNodeConfig, dlc_confidence_threshold: value}});
            }}/>}/>
        <details><summary className="text-sm">Convert a DLC model</summary>
            <div className="flex flex-col gap-2 p-1">
                <p className="text-sm">{readiness?.supported_model ?? 'Checking converter availability…'}</p>
                {readiness && !readiness.available && <p role="status" className="text-sm">{readiness.detail} Already converted models can still be selected above.</p>}
                <label className="flex flex-col text-sm">Pose configuration path<input className="input" value={poseConfig} onChange={event => setPoseConfig(event.target.value)}/></label>
                <label className="flex flex-col text-sm">Checkpoint path<input className="input" value={checkpoint} onChange={event => setCheckpoint(event.target.value)}/></label>
                <label className="flex flex-col text-sm">Project configuration path (optional connections)<input className="input" value={projectConfig} onChange={event => setProjectConfig(event.target.value)}/></label>
                <label className="flex flex-col text-sm">Input width<input className="input" type="number" min={32} max={8192} value={imageWidth} onChange={event => setImageWidth(Number(event.target.value))}/></label>
                <label className="flex flex-col text-sm">Input height<input className="input" type="number" min={32} max={8192} value={imageHeight} onChange={event => setImageHeight(Number(event.target.value))}/></label>
                <button className="button sm secondary" disabled={busy || job?.status === 'running' || job?.status === 'queued' || !readiness?.available || !poseConfig.trim() || !checkpoint.trim() || imageWidth < 32 || imageHeight < 32 || imageWidth > 8192 || imageHeight > 8192}
                    onClick={() => void perform(async () => setJob(await importDlcModel({pose_config_path: poseConfig.trim(), checkpoint_path: checkpoint.trim(), project_config_path: projectConfig.trim() || null, image_width: imageWidth, image_height: imageHeight}, lifetime.current?.signal)))}>Convert and select model</button>
                {job && <p role="status" className="text-sm">{job.status}: {job.detail}</p>}
                {error && job && ['queued', 'running'].includes(job.status) && <button className="button sm secondary" onClick={() => {setError(''); setJob({...job});}}>Retry status</button>}
            </div>
        </details>
        {error && <p role="alert" className="text-sm text-error" style={{whiteSpace: 'pre-wrap', overflowWrap: 'anywhere'}}>{error}</p>}
    </div>;
}

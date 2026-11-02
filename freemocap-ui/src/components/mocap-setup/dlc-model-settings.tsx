import {useEffect, useRef, useState} from 'react';
import ButtonSm from '@/components/ui-components/ButtonSm';
import TrackerSettingsDialog from './tracker-settings-dialog';
import {applyRealtimePipeline} from '@/store/slices/realtime/realtime-thunks';
import {pipelineConfigUpdated} from '@/store/slices/realtime/realtime-slice';
import type {RealtimePipelineConfig} from '@/store/slices/realtime/realtime-types';
import './dlc-model-settings.css';
import {useElectronIPC} from '@/services';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {mocapDlcSettingsChanged} from '@/store/slices/mocap';
import {useRealtimePipelineSync} from '@/hooks/useRealtimePipelineSync';
import {inspectDlcModel, importDlcModel, getDlcImportJob,
    type DlcModelMetadata, type DlcImportJob} from '@/services/server/dlc-models';
import SettingRow from '@/components/common/settings-layout/setting-row';
import SettingSelectInput from '@/components/common/settings-layout/setting-select-input';
import ValueSelector from '@/components/ui-components/ValueSelector';

/** One model-selection surface for all detector menus; Tracker owns model interpretation. */
export function DlcModelSettings({context, embedded = false}: {context: 'realtime' | 'posthoc'; embedded?: boolean}) {
    const [open, setOpen] = useState(false);
    if (embedded) return <DlcSettingsForm context={context}/>;
    return <><ButtonSm text="Configure DLC" buttonType="secondary" textColor="text-white" onClick={() => setOpen(true)}/>
        {open && <TrackerSettingsDialog title="DLC tracker" onClose={() => setOpen(false)}><DlcSettingsForm context={context}/></TrackerSettingsDialog>}</>;
}

function DlcSettingsForm({context}: {context: 'realtime' | 'posthoc'}) {
    const {api, isElectron} = useElectronIPC();
    const dispatch = useAppDispatch();
    const saved = useAppSelector(state => state.mocap.config);
    const {pipelineConfig, cameraNodeConfig, applyOrUpdatePipelineConfig, triggerRealtimeApply, isConnected, isLoading, error: pipelineError} = useRealtimePipelineSync();
    const selectedPath = context === 'realtime' ? cameraNodeConfig.dlc_model_path : saved.dlcModelPath;
    const confidence = context === 'realtime' ? cameraNodeConfig.dlc_confidence_threshold ?? 0.4 : saved.dlcConfidenceThreshold;
    const [modelPath, setModelPath] = useState(selectedPath ?? saved.dlcModelPath ?? '');
    const selectedGeometry = context === 'realtime' ? cameraNodeConfig.dlc_geometry_path : saved.dlcGeometryPath;
    const [geometryPath, setGeometryPath] = useState(selectedGeometry ?? '');
    useEffect(() => setGeometryPath(selectedGeometry ?? ''), [selectedGeometry]);
    const [metadata, setMetadata] = useState<DlcModelMetadata | null>(null);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [status, setStatus] = useState('');
    const [job, setJob] = useState<DlcImportJob | null>(null);
    const [selection, setSelection] = useState<{phase: 'applying' | 'selected' | 'failed'; model: DlcModelMetadata} | null>(null);
    const importId = useRef<string | null>(null);
    const preparing = job?.status === 'queued' || job?.status === 'running';
    const [poseConfig, setPoseConfig] = useState('');
    const [checkpoint, setCheckpoint] = useState('');
    const [projectConfig, setProjectConfig] = useState('');
    const [imageWidth, setImageWidth] = useState<number | null>(null);
    const [imageHeight, setImageHeight] = useState<number | null>(null);
    const lifetime = useRef<AbortController | null>(null);
    useEffect(() => {
        const controller = new AbortController();
        lifetime.current = controller;
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
    const applySettings = async (config: RealtimePipelineConfig) => {
        if (isConnected) await dispatch(applyRealtimePipeline(config)).unwrap();
        else dispatch(pipelineConfigUpdated(config));
    };
    const selectModel = async (model: DlcModelMetadata) => {
        setSelection({phase: 'applying', model});
        setStatus('');
        try {
            if (context === 'realtime') await applySettings({...pipelineConfig,
                camera_node_config: {...cameraNodeConfig, dlc_model_path: model.sidecar_path}});
            if (lifetime.current?.signal.aborted) return;
            setMetadata(model);
            setModelPath(model.sidecar_path);
            dispatch(mocapDlcSettingsChanged({dlcModelPath: model.sidecar_path}));
            setSelection({phase: 'selected', model});
        } catch (reason) {
            if (!lifetime.current?.signal.aborted) setSelection({phase: 'failed', model});
            throw reason;
        }
    };
    const selectModelRef = useRef(selectModel);
    selectModelRef.current = selectModel;
    useEffect(() => {
        if (!job || !['queued', 'running'].includes(job.status)) return;
        const controller = new AbortController();
        const timer = setTimeout(() => {
            getDlcImportJob(job.job_id, controller.signal).then(async result => {
                if (controller.signal.aborted || importId.current !== result.job_id) return;
                setJob(result);
                if (result.status === 'complete' && result.result) {
                    // Completing the job cleans up this polling effect. Model
                    // application outlives that poll, so its errors must use the
                    // component lifetime rather than the aborted poll signal.
                    setBusy(true);
                    try {await selectModelRef.current(result.result);} catch (reason) {
                        if (!lifetime.current?.signal.aborted) setError(errorMessage(reason));
                    } finally {if (!lifetime.current?.signal.aborted) setBusy(false);}
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
    const errorMessage = (reason: unknown) => reason && typeof reason === 'object' && 'message' in reason ? String(reason.message) : String(reason);
    const perform = async (action: () => Promise<void>) => {
        setBusy(true); setError(''); setStatus('Working…');
        try {await action();} catch (reason) {
            if (!lifetime.current?.signal.aborted) {
                setError(errorMessage(reason));
                setStatus('');
            }
        } finally {if (!lifetime.current?.signal.aborted) setBusy(false);}
    };
    const pickFile = async (title: string, extensions: string[], defaultPath?: string) => {
        if (!api || !isElectron) throw new Error('File selection is available in the FreeMoCap desktop app.');
        const path = await api.fileSystem.selectFile.mutate({title, defaultPath: defaultPath || undefined, filters: [{name: title, extensions}]});
        if (!path) setStatus('');
        return path;
    };
    const saveGeometry = async (path: string | null) => {
        if (context === 'realtime') await applySettings({...pipelineConfig, camera_node_config: {...cameraNodeConfig, dlc_geometry_path: path}});
        dispatch(mocapDlcSettingsChanged({dlcGeometryPath: path}));
        setGeometryPath(path ?? '');
        setStatus(path ? `Geometry saved. ${isConnected && context === 'realtime' ? 'Applied to the running pipeline.' : 'It will be validated when tracking starts.'}` : 'Geometry removed. Tracking keypoints only.');
    };
    const prepareProject = async (project: string, snapshot: string, useAnswers = false) => {
        if (!project) return;
        setSelection(null);
        setJob(null);
        importId.current = null;
        setStatus('Checking the project and latest checkpoint…');
        const next = await importDlcModel({project_config_path: project, ...(snapshot ? {checkpoint_path: snapshot} : {}),
            ...(useAnswers && poseConfig ? {pose_config_path: poseConfig} : {}),
            ...(useAnswers && imageWidth && imageHeight ? {image_width: imageWidth, image_height: imageHeight} : {})});
        importId.current = next.job_id;
        setJob(next); setStatus('');
    };
    const modelReady = !busy && !isLoading && !error && !!metadata && metadata.sidecar_path === selectedPath && !preparing && selection?.phase !== 'applying' && selection?.phase !== 'failed' && job?.status !== 'failed';
    const fileSummary = (path: string | null | undefined) => <p className="dlc-selected-file" title={path ?? ''}>{path ? path.split(/[\\/]/).pop() : 'No file selected'}</p>;
    return <div className="dlc-settings-form">
        <section className="dlc-section">
            <h2>1. Prepare your DLC model</h2>
            <p>Choose your project's config.yaml. Conversion starts automatically when needed, then the model is selected for tracking.</p>
            <ButtonSm text="Choose DLC project…" className="primary accent" textColor="text-white" disabled={busy || preparing || isLoading || !isElectron}
                onClick={() => void perform(async () => {
                    const path = await pickFile('Choose DLC project configuration', ['yaml','yml'], projectConfig);
                    if (path) {setPoseConfig(''); setImageWidth(null); setImageHeight(null); setProjectConfig(path); setCheckpoint(''); setStatus('Finding the latest checkpoint…'); await prepareProject(path, '');}
                })}/>{fileSummary(projectConfig)}
            <details open={job?.required_fields?.includes('checkpoint_path') || undefined}><summary>Choose a different checkpoint (optional)</summary>
            <p>Default: latest saved epoch in this project's training run.</p>
            <ButtonSm text="Choose checkpoint…" buttonType="secondary" textColor="text-white" disabled={busy || preparing || isLoading || !isElectron || !projectConfig}
                onClick={() => void perform(async () => {
                    const path = await pickFile('Choose DLC checkpoint', ['pt','pth'], checkpoint);
                    if (path) {setPoseConfig(''); setImageWidth(null); setImageHeight(null); setCheckpoint(path); setStatus('Checkpoint selected.'); await prepareProject(projectConfig, path);}
                })}/>{checkpoint && fileSummary(checkpoint)}
            {checkpoint && <ButtonSm text="Use latest checkpoint" buttonType="secondary" textColor="text-white" disabled={busy || preparing || isLoading} onClick={() => void perform(async () => {setCheckpoint(''); setPoseConfig(''); setImageWidth(null); setImageHeight(null); await prepareProject(projectConfig,'');})}/>}
            </details>
            {!isElectron && <p>Use the FreeMoCap desktop app for project and checkpoint file selection.</p>}
            {job?.stage === 'needs_input' && <div className="dlc-model-summary">
                <p>{job.detail}</p>
                {job.required_fields?.includes('pose_config_path') && <><ButtonSm text="Choose training configuration…" buttonType="secondary" textColor="text-white" disabled={!isElectron || busy}
                    onClick={() => void perform(async () => {const path = await pickFile('Choose training configuration', ['yaml','yml'], poseConfig); if (path) {setPoseConfig(path); setStatus('Training configuration selected. Retry preparation.');}})}/>{fileSummary(poseConfig)}</>}
                {job.required_fields?.includes('image_width') && <label>Model input width<input className="input-field" type="number" min={32} max={8192} value={imageWidth ?? ''} onChange={event => setImageWidth(Number(event.target.value))}/></label>}
                {job.required_fields?.includes('image_height') && <label>Model input height<input className="input-field" type="number" min={32} max={8192} value={imageHeight ?? ''} onChange={event => setImageHeight(Number(event.target.value))}/></label>}
            </div>}
            {job?.status === 'failed' && <ButtonSm text="Retry preparation" buttonType="secondary" textColor="text-white" disabled={busy || preparing} onClick={() => void perform(() => prepareProject(projectConfig,checkpoint,true))}/>}
        </section>
        <div aria-live="polite" className="dlc-feedback" data-state={selection?.phase ?? (preparing ? 'preparing' : modelReady ? 'selected' : 'idle')}>
            {preparing && <strong>Preparing model automatically</strong>}
            {selection?.phase === 'applying' && <strong>Model prepared — applying selection…</strong>}
            {selection?.phase === 'failed' && <><strong>Model prepared, but selection failed</strong>
                <p>The previous tracker selection has not been replaced. Fix the error below, then retry; conversion does not need to run again.</p>
                <ButtonSm text="Retry selection" buttonType="secondary" textColor="text-white" disabled={busy || isLoading}
                    onClick={() => void perform(() => selectModel(selection.model))}/></>}
            {modelReady && <><strong>Model ready and selected</strong>
                <p>{metadata!.keypoint_names.length} keypoints · {metadata!.input_size[1]} × {metadata!.input_size[0]} input</p>
                <p title={selectedPath ?? undefined}>Selected model: {metadata!.model_name}</p>
                <p className="dlc-next-step">{context === 'posthoc' ? 'Next: click Done, then start processing your recording.' : isConnected ? 'Selected in the running pipeline. Click Done to view tracking.' : 'Next: click Done, connect your cameras, then click the lightning bolt to start tracking.'}</p>
                <p>{selectedGeometry ? 'Object geometry is selected.' : 'For rigid-object pose, choose the geometry JSON below before clicking Done. Otherwise, track keypoints only.'}</p></>}
            {job?.resolved_checkpoint_path && <p title={job.resolved_checkpoint_path}>Checkpoint: {job.resolved_checkpoint_path.split(/[\\/]/).pop()}</p>}
            {job && <div><p>{job.status === 'complete' ? (job.cache_hit ? 'Reused a saved conversion.' : 'Conversion complete.') : job.detail}</p>
                <p>{Math.floor(job.elapsed_seconds ?? 0)} s elapsed{preparing ? (job.estimated_remaining_seconds == null ? ' · Time estimate unavailable until a conversion has been measured.' : job.estimated_remaining_seconds <= 0 ? ' · Taking longer than the estimate.' : ` · About ${Math.ceil(job.estimated_remaining_seconds)} s remaining`) : ''}</p></div>}
            {(busy || isLoading) && selection?.phase !== 'applying' && !preparing && <p role="status">{status || 'Working…'}</p>}
            {!busy && !isLoading && status && <p role="status">{status}</p>}
            {(error || (context === 'realtime' && pipelineError)) && <p role="alert">{error || pipelineError}</p>}
        </div>
        {metadata && <details className="dlc-model-summary"><summary>{modelReady ? 'Selected model details' : 'Previous tracker model (not the model being prepared)'}</summary>
            <p>{metadata.model_name}: {metadata.keypoint_names.length} keypoints</p>
            <p>{metadata.keypoint_names.join(', ')}</p><p>{metadata.connections.length} declared connections · {metadata.resize_method}</p>
        </details>}
        <details className="dlc-section"><summary>Load a different converted model (optional)</summary>
            <p>Use this only for a model that has already been converted. It replaces the selected model.</p>
            <ButtonSm text="Choose converted model…" className="primary accent" textColor="text-white" disabled={busy || preparing || isLoading || !isElectron}
                onClick={() => void perform(async () => {
                    const path = await pickFile('Choose DLC model', ['yaml','yml'], selectedPath ?? undefined);
                    if (path) {setJob(null); setSelection(null); importId.current = null; await selectModel(await inspectDlcModel(path, lifetime.current?.signal));}
                })}/>
            {!isElectron && <p>Open the FreeMoCap desktop app to use the file picker. For a remote server, advanced settings accept a path on that server.</p>}
            <details><summary>Advanced: server model path</summary>
                <label>Model file (.yaml)<input className="input-field" value={modelPath} onChange={event => setModelPath(event.target.value)}/></label>
                <ButtonSm text="Load model path" buttonType="secondary" textColor="text-white" disabled={busy || preparing || isLoading || !modelPath.trim()}
                    onClick={() => void perform(async () => {setJob(null); setSelection(null); importId.current = null; await selectModel(await inspectDlcModel(modelPath.trim(), lifetime.current?.signal));})}/>
            </details>
        </details>
        <section className="dlc-section"><h2>2. Tracking</h2>
        <SettingRow info={{title: "DLC execution provider", text: "Explicit ONNX CPU or CUDA execution in FP32. Session startup verifies availability; no automatic fallback."}} label="DLC execution provider" control={<SettingSelectInput label="DLC execution provider"
            value={saved.dlcExecutionProvider ?? 'cpu'} options={[{label: 'CPU · FP32', value: 'cpu'}, {label: 'CUDA · FP32', value: 'cuda'}]}
            onChange={(value: 'cpu' | 'cuda') => {dispatch(mocapDlcSettingsChanged({dlcExecutionProvider: value})); if (context === 'realtime') triggerRealtimeApply();}}/>}/>
        <SettingRow info={{title: "Keypoint confidence", text: "Suppress model keypoints below this confidence threshold."}} label="Keypoint confidence" control={<ValueSelector value={confidence} min={0} max={1} step={0.05} unit=""
            onChange={value => {
                if (context === 'posthoc') dispatch(mocapDlcSettingsChanged({dlcConfidenceThreshold: value}));
                else applyOrUpdatePipelineConfig({...pipelineConfig, camera_node_config: {...cameraNodeConfig, dlc_confidence_threshold: value}});
            }}/>}/>

            <label className="dlc-checkbox"><input type="checkbox" checked={context === 'realtime' ? pipelineConfig.aggregator_config.triangulation_enabled : saved.dlcTriangulationEnabled ?? false}
                onChange={event => {
                    const enabled = event.target.checked;
                    if (context === 'posthoc') dispatch(mocapDlcSettingsChanged({dlcTriangulationEnabled: enabled}));
                    else void perform(() => applySettings({...pipelineConfig, aggregator_config: {...pipelineConfig.aggregator_config, triangulation_enabled: enabled}}));
                }}/>Reconstruct 3D from calibrated cameras</label>
            <p>Requires at least two calibrated views. Leave off for 2D tracking.</p>
        </section>
        <section className="dlc-section"><h2>Rigid object geometry <span className="dlc-optional">Optional</span></h2>
            <p>Add a feature-definition JSON to fit the object's position and orientation. Its point names must match the loaded model. Leave blank for keypoints only.</p>
            <ButtonSm text="Choose geometry…" buttonType="secondary" textColor="text-white" disabled={busy || preparing || isLoading || !selectedPath || !isElectron}
                onClick={() => void perform(async () => {
                    const path = await pickFile('Choose object geometry', ['json'], selectedGeometry ?? undefined);
                    if (path) await saveGeometry(path);
                })}/>
            {fileSummary(selectedGeometry)}
            {selectedGeometry && <ButtonSm text="Remove geometry" buttonType="quaternary" textColor="text-white" disabled={busy || isLoading} onClick={() => void perform(() => saveGeometry(null))}/>}
            <details><summary>Advanced: server geometry path</summary>
                <label>Geometry file (.json)<input className="input-field" value={geometryPath} onChange={event => setGeometryPath(event.target.value)}/></label>
                <ButtonSm text="Save geometry path" buttonType="secondary" textColor="text-white" disabled={busy || isLoading || !selectedPath} onClick={() => void perform(() => saveGeometry(geometryPath.trim() || null))}/>
            </details>
            {!selectedPath && <p className="dlc-help">Load a model before adding geometry.</p>}
        </section>
    </div>;
}

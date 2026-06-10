import {useNavigate} from 'react-router-dom';
import {useAppDispatch} from '@/store/hooks';
import {activeRecordingSet} from '@/store/slices/active-recording/active-recording-slice';
import {useElectronIPC} from '@/services';
import {PipelineGroup, PipelinePhase, PipelineProgress, PHASE_LABELS, PIPELINE_TYPE_CONFIG} from '@/store/slices/pipelines';
import {stopPipeline} from '@/store/slices/pipelines/pipelines-thunks';

function formatTimeAgo(timestamp: number): string {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
}

function SubProgressBar({pipeline, label, isAggregator = false}: {
    pipeline: PipelineProgress;
    label: string;
    isAggregator?: boolean;
}) {
    const isFailed = pipeline.phase === PipelinePhase.FAILED;
    const isComplete = pipeline.phase === PipelinePhase.COMPLETE;
    const isTerminal = isComplete || isFailed;
    const isIndeterminate = isAggregator && !isTerminal && pipeline.phase !== PipelinePhase.SETTING_UP;

    const rightText = isTerminal && pipeline.completedAt
        ? formatTimeAgo(pipeline.completedAt)
        : isIndeterminate
            ? (pipeline.detail || PHASE_LABELS[pipeline.phase])
            : `${pipeline.progress}%`;

    const progressColor = isFailed ? 'var(--color-error)' : isComplete ? 'var(--color-success)' : 'var(--color-info)';

    return (
        <div className="mb-1" style={{opacity: isTerminal ? 0.6 : 1}}>
            <div className="flex flex-row justify-content-space-between items-center" style={{marginBottom: 1}}>
                <p className="text sm text-gray flex-1 mr-1 m-0" style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.68rem'}}>
                    {label}
                </p>
                <p className="text sm text-gray flex-shrink-0 m-0" style={{fontSize: '0.65rem', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    {rightText}
                </p>
            </div>
            <div className="update-progress-track" style={{height: 4, borderRadius: 2}}>
                {!isIndeterminate && (
                    <div className="update-progress-fill h-full" style={{width: `${pipeline.progress}%`, backgroundColor: progressColor, borderRadius: 2}}/>
                )}
                {isIndeterminate && (
                    <div className="h-full" style={{width: '40%', backgroundColor: progressColor, borderRadius: 2, animation: 'indeterminateProgress 1.5s infinite ease-in-out'}}/>
                )}
            </div>
            {isFailed && pipeline.detail && (
                <p
                    title={pipeline.detail}
                    className="text sm text-error block m-0"
                    style={{fontSize: '0.62rem', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', cursor: 'default'}}
                >
                    {pipeline.detail}
                </p>
            )}
        </div>
    );
}

export default function PipelineGroupCard({group, onDismiss}: {
    group: PipelineGroup;
    onDismiss?: () => void;
}) {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const {api} = useElectronIPC();

    const overallProgress =
        group.aggregator?.progress ??
        (group.videoNodes.length > 0
            ? Math.round(group.videoNodes.reduce((sum, n) => sum + n.progress, 0) / group.videoNodes.length)
            : 0);

    const borderColor = group.isFailed ? 'var(--color-error)' : group.isComplete ? 'var(--color-success)' : 'var(--color-border-secondary)';
    const typeConfig = group.pipelineType ? PIPELINE_TYPE_CONFIG[group.pipelineType] : null;
    const fullPath = group.recordingPath || undefined;
    const recordingName = group.recordingName;
    const pipelineId = group.basePipelineId;

    const handleOpenFolder = async () => {
        if (!fullPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({path: fullPath});
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    };

    const handleLoadPlayback = () => {
        if (!group.recordingName) return;
        dispatch(activeRecordingSet({
            recordingName: group.recordingName,
            origin: 'browsed',
        }));
        navigate('/playback');
    };

    return (
        <div className="br-1" style={{margin: '6px 8px', padding: 8, border: `1px solid ${borderColor}`, opacity: group.isActive ? 1 : 0.6}}>
            <div className="flex flex-row items-center mb-1">
                {typeConfig && (
                    <div className="flex-shrink-0 br-1" style={{
                        padding: '1px 6px', marginRight: 6,
                        backgroundColor: typeConfig.color + '22',
                        border: `1px solid ${typeConfig.color}66`,
                    }}>
                        <p className="text sm m-0" style={{fontSize: '0.62rem', fontWeight: 600, color: typeConfig.color, lineHeight: 1.4}}>
                            {typeConfig.label}
                        </p>
                    </div>
                )}
                <p className="text sm flex-1 min-w-0 m-0" style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    <span className="text-gray">Pipeline: </span>
                    <span style={{fontWeight: 'bold'}}>{pipelineId}</span>
                </p>

                <p className="text sm text-gray flex-shrink-0 m-0" style={{fontSize: '0.7rem'}}>
                    {overallProgress}%
                </p>
                <button title="Open folder" className="button icon-button br-1 p-01" onClick={handleOpenFolder} disabled={!fullPath}>
                    <span className="icon load-icon icon-size-20" style={{fontSize: '0.85rem'}}/>
                </button>
                <button title="Load in playback" className="button icon-button br-1 p-01" onClick={handleLoadPlayback}>
                    <span className="icon play-icon icon-size-20" style={{fontSize: '0.85rem'}}/>
                </button>
                {group.isActive && (
                    <button
                        title="Stop pipeline"
                        className="button icon-button br-1 p-01"
                        onClick={() => dispatch(stopPipeline(group.basePipelineId))}
                        style={{color: 'var(--color-error)'}}
                    >
                        <span className="icon close-icon icon-size-20" style={{fontSize: '0.85rem'}}/>
                    </button>
                )}
                {onDismiss && (
                    <button className="button icon-button br-1 p-01" onClick={onDismiss}>
                        <span className="icon close-icon icon-size-20" style={{fontSize: '0.75rem'}}/>
                    </button>
                )}
            </div>
            <div title={fullPath}>
                <p className="text sm flex-1 min-w-0 m-0" style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    <span className="text-gray">Recording: </span>
                    <span style={{fontWeight: 'bold'}}>{recordingName}</span>
                </p>
            </div>
            {group.videoNodes.length > 0 && (
                <div className="pl-2" style={{borderLeft: '2px solid var(--color-border-secondary)', marginBottom: group.aggregator ? 6 : 0}}>
                    {group.videoNodes.map((node) => {
                        const cameraId = node.pipelineId.includes(':')
                            ? node.pipelineId.split(':').slice(1).join(':')
                            : node.pipelineId;
                        return <SubProgressBar key={node.pipelineId} pipeline={node} label={`Camera: ${cameraId}`}/>;
                    })}
                </div>
            )}

            {group.aggregator && (
                <div className="mt-1">
                    <SubProgressBar
                        pipeline={group.aggregator}
                        isAggregator={true}
                        label={
                            group.aggregator.phase === PipelinePhase.COMPLETE
                                ? 'Aggregation complete'
                                : group.aggregator.phase === PipelinePhase.FAILED
                                    ? 'Aggregation failed'
                                    : group.videoNodes.length > 0
                                        ? `Aggregating ${group.videoNodes.length} camera${group.videoNodes.length !== 1 ? 's' : ''}`
                                        : PHASE_LABELS[group.aggregator.phase]
                        }
                    />
                </div>
            )}
        </div>
    );
}

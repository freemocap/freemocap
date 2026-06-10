import {PipelineProgress, PipelinePhase, PHASE_LABELS} from '@/store/slices/pipelines';

function formatTimeAgo(timestamp: number): string {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
}

interface PipelineProgressBarProps {
    pipeline: PipelineProgress;
}

export default function PipelineProgressBar({pipeline}: PipelineProgressBarProps) {
    const phaseLabel = PHASE_LABELS[pipeline.phase] ?? pipeline.phase;
    const isFailed = pipeline.phase === PipelinePhase.FAILED;
    const isComplete = pipeline.phase === PipelinePhase.COMPLETE;
    const isTerminal = isComplete || isFailed;

    const progressColor = isFailed ? 'var(--color-error)' : isComplete ? 'var(--color-success)' : 'var(--color-info)';

    return (
        <div style={{padding: '4px 8px', opacity: isTerminal ? 0.5 : 1}}>
            <div className="flex flex-row justify-content-space-between items-center" style={{marginBottom: 2}}>
                <p className="text sm text-white flex-1 mr-1 m-0" style={{fontWeight: 'bold', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    {pipeline.pipelineType} — {pipeline.pipelineId}
                </p>
                <p className="text sm text-gray m-0 flex-shrink-0">
                    {isTerminal && pipeline.completedAt
                        ? `${phaseLabel} ${formatTimeAgo(pipeline.completedAt)}`
                        : `${phaseLabel} ${pipeline.progress}%`
                    }
                </p>
            </div>
            <div className="update-progress-track">
                <div className="update-progress-fill" style={{width: `${pipeline.progress}%`, backgroundColor: progressColor}}/>
            </div>
            {pipeline.detail && (
                <p className="text sm text-gray block m-0" style={{marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'}}>
                    {pipeline.detail}
                </p>
            )}
        </div>
    );
}

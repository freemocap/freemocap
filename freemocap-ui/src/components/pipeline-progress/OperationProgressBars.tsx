import {formatProcessingDuration} from './ProcessingTiming';
import type {TaskOperation} from '@/services/server/transport/message-contract';

const STATUS_LABELS: Record<TaskOperation['status'], string> = {
    waiting: 'Waiting', running: 'Running', complete: 'Complete', failed: 'Failed', cancelled: 'Stopped',
};

/** Each row displays one backend operation; no client-side scheduling or aggregate percentage. */
export default function OperationProgressBars({operations}: {operations: readonly TaskOperation[]}) {
    return <div className="flex flex-col gap-2" aria-label="Processing tasks">
        {operations.map(operation => {
            const {operation_id, label, status, progress_fraction, completed, total, unit, detail} = operation;
            const percent = progress_fraction === null ? undefined : Math.round(progress_fraction * 100);
            const indeterminate = status === 'running' && percent === undefined;
            const color = status === 'failed' ? 'var(--color-error)'
                : status === 'complete' ? 'var(--color-success)'
                : status === 'running' ? 'var(--color-info)' : 'var(--color-text-secondary)';
            const count = completed === null ? null : `${completed.toLocaleString()}${total === null ? '' : ` / ${total.toLocaleString()}`}${unit ? ` ${unit}` : ''}`;
            const stateLabel = STATUS_LABELS[status];
            return <div key={operation_id} data-operation-id={operation_id} data-status={status} className="flex flex-col gap-1">
                <div className="flex items-center gap-2" style={{justifyContent: 'space-between', flexWrap: 'wrap'}}>
                    <span className="text md m-0" style={{overflowWrap: 'anywhere'}}>{label}</span>
                    <div className="flex items-center gap-2" style={{marginLeft: 'auto', flexWrap: 'wrap', justifyContent: 'flex-end'}}>
                        {operation.elapsed_seconds != null && <span className="text sm" style={{opacity: 0.8, whiteSpace: 'nowrap'}}>{formatProcessingDuration(operation.elapsed_seconds)}</span>}
                        {operation.seconds_per_motion_frame != null && <span className="text sm" style={{opacity: 0.8, whiteSpace: 'nowrap'}}>{(operation.seconds_per_motion_frame * 1000).toLocaleString(undefined, {maximumFractionDigits: 1})} ms / mocap frame</span>}
                    <span className="text md m-0" style={{whiteSpace: 'nowrap', color}}>{stateLabel}{percent === undefined ? '' : ` · ${percent}%`}</span>
                    </div>
                </div>
                <div className="sub-progress-track" role="progressbar" aria-label={label}
                    aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
                    aria-valuetext={`${stateLabel}${count ? `: ${count}` : ''}`}>
                    <div className={indeterminate ? 'h-full sub-progress-indeterminate' : 'h-full sub-progress-fill'}
                        style={{backgroundColor: color, ...(indeterminate ? {} : {width: `${status === 'complete' ? 100 : percent ?? 0}%`})}}/>
                </div>
                {count && <span className="text sm m-0">{count}</span>}
                {detail && <details className="text sm"><summary>Details</summary><div style={{overflowWrap: 'anywhere'}}>{detail}</div></details>}
            </div>;
        })}
    </div>;
}

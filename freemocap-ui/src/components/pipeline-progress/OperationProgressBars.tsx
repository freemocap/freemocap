import {formatProcessingDuration} from './ProcessingTiming';
import type {ProcessingPlan, TaskOperation} from '@/services/server/transport/message-contract';
import {operationGroups, type OperationGroup} from '@/components/processing-graph/graph-model';

const STATUS_LABELS: Record<TaskOperation['status'], string> = {
    waiting: 'Waiting', running: 'Running', complete: 'Complete', failed: 'Failed', cancelled: 'Stopped',
};

/** One backend operation: its state, counts with units, and timing. No client-side scheduling or aggregate percentage. */
function OperationRow({operation, title}: {operation: TaskOperation; title: string}) {
    const {operation_id, label, status, progress_fraction, completed, total, unit, detail} = operation;
    const percent = progress_fraction === null ? undefined : Math.round(progress_fraction * 100);
    const indeterminate = status === 'running' && percent === undefined;
    const color = status === 'failed' ? 'var(--color-danger)'
        : status === 'complete' ? 'var(--color-success)'
        : status === 'running' ? 'var(--color-info)' : 'var(--color-text-secondary)';
    const count = completed === null ? null : `${completed.toLocaleString()}${total === null ? '' : ` / ${total.toLocaleString()}`}${unit ? ` ${unit}` : ''}`;
    const stateLabel = STATUS_LABELS[status];
    return <div data-operation-id={operation_id} data-status={status} className="flex flex-col gap-1">
        <div className="flex items-center gap-2" style={{justifyContent: 'space-between', flexWrap: 'wrap'}}>
            <span className="text md m-0" title={label} style={{overflowWrap: 'anywhere'}}>{title}</span>
            <div className="flex items-center gap-2" style={{marginLeft: 'auto', flexWrap: 'wrap', justifyContent: 'flex-end'}}>
                {operation.elapsed_seconds != null && <span className="text sm" style={{opacity: 0.8, whiteSpace: 'nowrap'}}>{formatProcessingDuration(operation.elapsed_seconds)}</span>}
                {operation.seconds_per_motion_frame != null && <span className="text sm" style={{opacity: 0.8, whiteSpace: 'nowrap'}}>{(operation.seconds_per_motion_frame * 1000).toLocaleString(undefined, {maximumFractionDigits: 1})} ms / mocap frame</span>}
                <span className="text md m-0" style={{whiteSpace: 'nowrap', color}}>{stateLabel}{percent === undefined ? '' : ` · ${percent}%`}</span>
            </div>
        </div>
        <div className="sub-progress-track" role="progressbar" aria-label={title}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}
            aria-valuetext={`${stateLabel}${count ? `: ${count}` : ''}`}>
            <div className={indeterminate ? 'h-full sub-progress-indeterminate' : 'h-full sub-progress-fill'}
                style={{backgroundColor: color, ...(indeterminate ? {} : {width: `${status === 'complete' ? 100 : percent ?? 0}%`})}}/>
        </div>
        {count && <span className="text sm m-0">{count}</span>}
        {detail && <details className="text sm"><summary>Details</summary><div style={{overflowWrap: 'anywhere'}}>{detail}</div></details>}
    </div>;
}

/** A task's operation bars. With a plan, every bar is listed from launch, grouped by processing stage in the plan's order,
 *  and named as in the processing graph; without one, bars follow the server's order and labels. */
export default function OperationProgressBars({operations, plan}: {operations: TaskOperation[]; plan: ProcessingPlan | null}) {
    if (!plan) {
        return <div className="flex flex-col gap-2" aria-label="Processing tasks">
            {operations.map(operation => <OperationRow key={operation.operation_id} operation={operation} title={operation.label}/>)}
        </div>;
    }
    let groups: OperationGroup[];
    try {
        groups = operationGroups(plan, operations);
    } catch (reason) {
        return <p role="alert" className="text sm m-0" style={{color: 'var(--color-danger-text)'}}>
            {reason instanceof Error ? reason.message : String(reason)}</p>;
    }
    return <div className="flex flex-col gap-3" aria-label="Processing tasks">
        {groups.map(group => <section key={group.stageNumber} className="flex flex-col gap-2"
            aria-label={group.stageNumber ? `Stage ${group.stageNumber}: ${group.stageLabel}` : 'Other operations'}>
            <span className="text sm m-0" style={{opacity: 0.7}}>
                {group.stageNumber ? `Stage ${group.stageNumber} · ${group.stageLabel}` : 'Other operations'}</span>
            {group.rows.map(row => <OperationRow key={row.operation.operation_id} operation={row.operation} title={row.title}/>)}
        </section>)}
    </div>;
}

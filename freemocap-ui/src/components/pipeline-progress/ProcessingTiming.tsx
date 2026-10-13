import type {TaskTiming} from '@/services/server/transport/message-contract';

export function formatProcessingDuration(seconds: number): string {
    if (seconds < 1) return `${(seconds * 1000).toLocaleString(undefined, {maximumFractionDigits: 1})} ms`;
    if (seconds < 60) return `${seconds.toLocaleString(undefined, {maximumFractionDigits: 1})} s`;
    const rounded = Math.round(seconds);
    const hours = Math.floor(rounded / 3600);
    const minutes = Math.floor((rounded % 3600) / 60);
    return `${hours ? `${hours} h ` : ''}${minutes} m ${rounded % 60} s`;
}

/** Values come from the backend, including the synchronized motion-frame denominator. */
export default function ProcessingTiming({timing, running}: {timing: TaskTiming | null; running: boolean}) {
    if (!timing) return null;
    return <div className="flex flex-col gap-1 text sm" aria-label="Processing time">
        <span>{running ? 'Elapsed' : 'Duration'} {formatProcessingDuration(timing.elapsed_seconds)}</span>
        {timing.seconds_per_motion_frame !== null && <span>
            {(timing.seconds_per_motion_frame * 1000).toLocaleString(undefined, {maximumFractionDigits: 1})} ms / motion-capture frame
        </span>}
        {timing.motion_frame_count !== null && <span>{timing.motion_frame_count.toLocaleString()} motion-capture frames (all cameras together)</span>}
    </div>;
}

const CHANNEL_NAME = 'freemocap-realtime-pipeline';

export type RealtimePipelineBroadcastState = {
    isConnected: boolean;
    logPipelineTimes: boolean;
};

export type RealtimePipelineBroadcastMessage =
    | {type: 'state'; state: RealtimePipelineBroadcastState}
    | {type: 'request-state'}
    | {type: 'set-log-pipeline-times'; enabled: boolean};

function getChannel(): BroadcastChannel | null {
    if (typeof BroadcastChannel === 'undefined') {
        return null;
    }
    return new BroadcastChannel(CHANNEL_NAME);
}

export function broadcastRealtimePipelineState(state: RealtimePipelineBroadcastState): void {
    const channel = getChannel();
    if (!channel) return;
    channel.postMessage({type: 'state', state} satisfies RealtimePipelineBroadcastMessage);
    channel.close();
}

export function requestRealtimePipelineState(): void {
    const channel = getChannel();
    if (!channel) return;
    channel.postMessage({type: 'request-state'} satisfies RealtimePipelineBroadcastMessage);
    channel.close();
}

export function broadcastSetLogPipelineTimes(enabled: boolean): void {
    const channel = getChannel();
    if (!channel) return;
    channel.postMessage({type: 'set-log-pipeline-times', enabled} satisfies RealtimePipelineBroadcastMessage);
    channel.close();
}

export function subscribeRealtimePipelineBroadcast(
    onMessage: (message: RealtimePipelineBroadcastMessage) => void,
): () => void {
    const channel = getChannel();
    if (!channel) {
        return () => {};
    }

    const handler = (event: MessageEvent<RealtimePipelineBroadcastMessage>): void => {
        onMessage(event.data);
    };
    channel.addEventListener('message', handler);
    return () => {
        channel.removeEventListener('message', handler);
        channel.close();
    };
}

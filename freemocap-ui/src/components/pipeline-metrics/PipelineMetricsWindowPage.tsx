import React, {useEffect, useMemo, useState} from 'react';
import {PipelineNetworkTimeline} from '@/components/pipeline-metrics/PipelineNetworkTimeline';
import {
    buildTimelineViewModel,
    DEFAULT_CATEGORY_FILTERS,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import type {PipelineTimelineSnapshot} from '@/services/server/server-helpers/pipeline-timing-store';
import {useMetricsServer} from '@/services/server/MetricsServerContextProvider';
import {broadcastSetLogPipelineTimes, type RealtimePipelineBroadcastState} from '@/services/realtime-pipeline-broadcast';
import IconButton from '@/components/ui-components/IconButton';
import ToggleComponent from '@/components/ui-components/ToggleComponent';

const POLL_MS = 200;

export default function PipelineMetricsWindowPage(): React.ReactElement {
    const {isConnected, getPipelineTimingStore} = useMetricsServer();

    const [paused, setPaused] = useState(false);
    const [tick, setTick] = useState(0);
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [frozenSnapshot, setFrozenSnapshot] = useState<PipelineTimelineSnapshot | null>(null);
    const [broadcastPipelineState, setBroadcastPipelineState] = useState<RealtimePipelineBroadcastState | null>(null);

    useEffect(() => {
        const channel = new BroadcastChannel('freemocap-realtime-pipeline');
        let retryHandle: ReturnType<typeof setInterval> | null = null;
        const handler = (event: MessageEvent) => {
            const message = event.data;
            if (message?.type === 'state') {
                setBroadcastPipelineState(message.state);
                // Stop retrying once we have a response
                if (retryHandle !== null) {
                    clearInterval(retryHandle);
                    retryHandle = null;
                }
            }
        };
        channel.addEventListener('message', handler);
        // Request state immediately, then retry every 500ms until we get a response
        channel.postMessage({type: 'request-state'});
        retryHandle = setInterval(() => {
            channel.postMessage({type: 'request-state'});
        }, 500);
        return () => {
            channel.removeEventListener('message', handler);
            if (retryHandle !== null) {
                clearInterval(retryHandle);
            }
            channel.close();
        };
    }, []);

    useEffect(() => {
        if (paused) return;
        const id = setInterval(() => setTick(t => t + 1), POLL_MS);
        return () => clearInterval(id);
    }, [paused]);

    useEffect(() => {
        if (paused) {
            setFrozenSnapshot(getPipelineTimingStore().getTimelineSnapshot());
        } else {
            setFrozenSnapshot(null);
        }
    }, [paused, getPipelineTimingStore]);

    void tick;
    const timelineData = paused && frozenSnapshot
        ? frozenSnapshot
        : getPipelineTimingStore().getTimelineSnapshot();

    const model = useMemo(() => buildTimelineViewModel({
        events: timelineData.events,
        backendFrameDurationMs: timelineData.backendFrameDurationMs,
        lockedFrameDurationMs: timelineData.lockedFrameDurationMs,
        droppedTimingEvents: timelineData.droppedTimingEvents,
        logPipelineTimesEnabled: timelineData.logPipelineTimesEnabled,
        categoryFilters: DEFAULT_CATEGORY_FILTERS,
        paused,
    }), [timelineData, paused]);

    const pipelineStatusKnown = timelineData.realtimePipelineActive != null || broadcastPipelineState != null;
    const pipelineConnected = timelineData.realtimePipelineActive === true
        || (timelineData.realtimePipelineActive == null && broadcastPipelineState?.isConnected === true);
    const logTimes = timelineData.realtimePipelineActive != null
        ? timelineData.logPipelineTimesEnabled
        : broadcastPipelineState?.logPipelineTimes !== false;

    const alertStyle: React.CSSProperties = {
        margin: '0 8px',
        padding: '8px 12px',
        borderRadius: 4,
        backgroundColor: 'var(--gray-800)',
        fontSize: '12px',
        color: 'var(--gray-300)',
    };

    return (
        <div
            style={{
                height: '100vh',
                display: 'flex',
                flexDirection: 'column',
                backgroundColor: 'var(--gray-900)',
            }}
        >
            {/* Toolbar */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                flexWrap: 'wrap',
                minHeight: 44,
                padding: '0 8px',
                borderBottom: '1px solid var(--gray-700)',
            }}>
                <span className="title" style={{fontWeight: 700, marginRight: 4}}>
                    Pipeline metrics
                </span>
                <span className="text md" style={{color: isConnected ? 'var(--green-300)' : 'var(--gray-400)'}}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                </span>
                {model.latestFrame != null && (
                    <span className="text md" style={{color: 'var(--gray-400)'}}>
                        Frames {model.frameStart}–{model.frameEnd} (latest F{model.latestFrame})
                    </span>
                )}
                {model.droppedTimingEvents > 0 && (
                    <span className="text md" style={{color: 'var(--warning-400)'}}>
                        Dropped events: {model.droppedTimingEvents}
                    </span>
                )}
                <div style={{flex: 1}} />
                <IconButton
                    icon={paused ? 'play-icon' : 'pause-icon'}
                    title={paused ? 'Resume' : 'Pause'}
                    onClick={() => setPaused(p => !p)}
                />
                {pipelineConnected && (
                    <ToggleComponent
                        text="Timing"
                        isToggled={logTimes}
                        onToggle={(checked) => broadcastSetLogPipelineTimes(checked)}
                    />
                )}
            </div>

            {/* Alerts */}
            {pipelineStatusKnown && !pipelineConnected && (
                <div style={{...alertStyle, borderLeft: '3px solid var(--green-500)'}}>
                    Connect the realtime pipeline to collect pipeline stage timings.
                </div>
            )}
            {!pipelineStatusKnown && isConnected && (
                <div style={{...alertStyle, borderLeft: '3px solid var(--green-500)'}}>
                    Waiting for pipeline status from the server…
                </div>
            )}
            {pipelineConnected && !logTimes && (
                <div style={{...alertStyle, borderLeft: '3px solid var(--warning-400)'}}>
                    Pipeline timing is disabled on the server.
                </div>
            )}

            {/* Timeline */}
            <div style={{
                flex: 1,
                minHeight: 0,
                margin: '0 8px 8px',
                border: '1px solid var(--gray-700)',
                borderRadius: 4,
                overflow: 'hidden',
            }}>
                <PipelineNetworkTimeline
                    model={model}
                    selectedTaskId={selectedTaskId}
                    onSelectTask={setSelectedTaskId}
                />
            </div>
        </div>
    );
}

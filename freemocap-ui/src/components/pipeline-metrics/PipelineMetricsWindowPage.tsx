import React, {useEffect, useMemo, useState} from 'react';
import {PipelineNetworkTimeline} from '@/components/pipeline-metrics/PipelineNetworkTimeline';
import {
    buildTimelineViewModel,
    DEFAULT_CATEGORY_FILTERS,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import type {PipelineTimelineSnapshot} from '@/services/server/server-helpers/pipeline-timing-store';
import {useMetricsServer} from '@/services/server/MetricsServerContextProvider';
import {broadcastSetLogPipelineTimes, type RealtimePipelineBroadcastState} from '@/services/realtime-pipeline-broadcast';
import {serverUrls} from '@/constants/server-urls';
import IconButton from '@/components/ui-components/IconButton';
import ToggleComponent from '@/components/ui-components/ToggleComponent';

const POLL_MS = 200;

interface GpuInfo {
    gpus: {name: string; vram_gb: string | null}[];
    onnx_version: string | null;
    onnx_providers: string[];
    gpu_acceleration_available: boolean;
    optimal_provider: string;
}

export default function PipelineMetricsWindowPage(): React.ReactElement {
    const {isConnected, getPipelineTimingStore} = useMetricsServer();

    const [paused, setPaused] = useState(false);
    const [tick, setTick] = useState(0);
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [frozenSnapshot, setFrozenSnapshot] = useState<PipelineTimelineSnapshot | null>(null);
    const [broadcastPipelineState, setBroadcastPipelineState] = useState<RealtimePipelineBroadcastState | null>(null);
    const [gpuInfo, setGpuInfo] = useState<GpuInfo | null>(null);

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

    useEffect(() => {
        fetch(serverUrls.endpoints.gpuInfo)
            .then(r => r.json())
            .then(setGpuInfo)
            .catch(() => {});
    }, []);

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

    const displayedMeanMs = useMemo(() => {
        const snapshot = getPipelineTimingStore().getSnapshot();
        const val = snapshot.recentValues.get("skeleton_inference:predict_batch");
        return val ?? null;
    }, [timelineData]);

    const trailingMeanMs = timelineData?.trailingMeanFrameMs ?? null;

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
                flexDirection: 'column',
                padding: '4px 8px',
                borderBottom: '1px solid var(--gray-700)',
                gap: '2px',
            }}>
                {/* Row 1: title, status, GPU info, controls */}
                <div style={{display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap'}}>
                    <span className="title" style={{fontWeight: 700, marginRight: 4}}>
                        Pipeline metrics
                    </span>
                    <span className="text md" style={{color: isConnected ? 'var(--green-300)' : 'var(--gray-400)'}}>
                        {isConnected ? 'Connected' : 'Disconnected'}
                    </span>
                    <div style={{flex: 1}} />
                    {gpuInfo && (
                        <span className="text sm" style={{color: 'var(--gray-500)'}}>
                            {gpuInfo.gpus.length > 0 && gpuInfo.gpus[0].vram_gb
                                ? `${gpuInfo.gpus[0].name} (${gpuInfo.gpus[0].vram_gb})`
                                : gpuInfo.gpus.length > 0
                                    ? gpuInfo.gpus[0].name
                                    : 'CPU'}
                            {' · '}
                            {gpuInfo.optimal_provider
                                .replace('TensorrtExecutionProvider', 'TensorRT')
                                .replace('CUDAExecutionProvider', 'CUDA')
                                .replace('CPUExecutionProvider', 'CPU')}
                        </span>
                    )}
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
                {/* Row 2: frame timing */}
                {displayedMeanMs != null && (
                    <div style={{display: 'flex', gap: '12px'}}>
                        <span className="text md" style={{color: 'var(--gray-400)'}}>
                            Average frame processing time: {displayedMeanMs.toFixed(1)} ms
                            {trailingMeanMs != null && (
                                <span style={{color: 'var(--gray-500)'}}> · 10s avg: {trailingMeanMs.toFixed(1)} ms</span>
                            )}
                        </span>
                    </div>
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

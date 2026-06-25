import React, {useEffect, useMemo, useState} from 'react';
import {
    Alert,
    Box,
    Checkbox,
    FormControlLabel,
    FormGroup,
    IconButton,
    Switch,
    Toolbar,
    Typography,
} from '@mui/material';
import PauseIcon from '@mui/icons-material/Pause';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import {useTheme} from '@mui/material/styles';
import {PipelineNetworkTimeline} from '@/components/pipeline-metrics/PipelineNetworkTimeline';
import {
    buildTimelineViewModel,
    DEFAULT_CATEGORY_FILTERS,
    type TimelineCategoryFilters,
} from '@/components/pipeline-metrics/pipelineTimelineModel';
import {CATEGORY_COLORS} from '@/components/pipeline-metrics/pipelineTaskTopology';
import type {PipelineTaskCategory} from '@/services/server/server-helpers/pipeline-timing-types';
import type {PipelineTimelineSnapshot} from '@/services/server/server-helpers/pipeline-timing-store';
import {useMetricsServer} from '@/services/server/MetricsServerContextProvider';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {applyRealtimePipeline, selectIsPipelineConnected, selectPipelineConfig} from '@/store/slices/realtime';

const POLL_MS = 200;
const CATEGORY_LABELS: Record<PipelineTaskCategory, string> = {
    capture: 'Capture',
    tracking: 'Tracking',
    aggregation: 'Aggregation',
    ui_backend: 'Server preview',
    ui_frontend: 'UI render',
    other: 'Other',
};

export default function PipelineMetricsWindowPage(): React.ReactElement {
    const theme = useTheme();
    const {isConnected, getPipelineTimingStore} = useMetricsServer();
    const dispatch = useAppDispatch();
    const pipelineConfig = useAppSelector(selectPipelineConfig);
    const pipelineConnected = useAppSelector(selectIsPipelineConnected);
    const logTimes = pipelineConfig.log_pipeline_times !== false;

    const [paused, setPaused] = useState(false);
    const [tick, setTick] = useState(0);
    const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
    const [categoryFilters, setCategoryFilters] = useState<TimelineCategoryFilters>(DEFAULT_CATEGORY_FILTERS);
    const [frozenSnapshot, setFrozenSnapshot] = useState<PipelineTimelineSnapshot | null>(null);

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
        categoryFilters,
        paused,
    }), [timelineData, categoryFilters, paused]);

    const handleToggleTiming = (_: unknown, checked: boolean): void => {
        dispatch(applyRealtimePipeline({
            ...pipelineConfig,
            log_pipeline_times: checked,
        }));
    };

    const toggleCategory = (cat: PipelineTaskCategory): void => {
        setCategoryFilters(prev => ({...prev, [cat]: !prev[cat]}));
    };

    return (
        <Box
            sx={{
                height: '100vh',
                display: 'flex',
                flexDirection: 'column',
                bgcolor: theme.palette.background.default,
            }}
        >
            <Toolbar variant="dense" sx={{gap: 1, flexWrap: 'wrap', minHeight: 44}}>
                <Typography variant="subtitle2" sx={{fontWeight: 700, mr: 1}}>
                    Pipeline metrics
                </Typography>
                <Typography variant="caption" color={isConnected ? 'success.main' : 'text.secondary'}>
                    {isConnected ? 'Connected' : 'Disconnected'}
                </Typography>
                {model.latestFrame != null && (
                    <Typography variant="caption" color="text.secondary">
                        Frames {model.frameStart}–{model.frameEnd} (latest F{model.latestFrame})
                    </Typography>
                )}
                {model.droppedTimingEvents > 0 && (
                    <Typography variant="caption" color="warning.main">
                        Dropped events: {model.droppedTimingEvents}
                    </Typography>
                )}
                <Box sx={{flex: 1}} />
                <IconButton size="small" onClick={() => setPaused(p => !p)} aria-label={paused ? 'Resume' : 'Pause'}>
                    {paused ? <PlayArrowIcon fontSize="small" /> : <PauseIcon fontSize="small" />}
                </IconButton>
                {pipelineConnected && (
                    <FormControlLabel
                        control={<Switch checked={logTimes} onChange={handleToggleTiming} size="small" />}
                        label={<Typography variant="caption">Timing</Typography>}
                    />
                )}
            </Toolbar>

            {!pipelineConnected && (
                <Alert severity="info" sx={{mx: 1}}>
                    Connect the realtime pipeline to collect pipeline stage timings.
                </Alert>
            )}
            {pipelineConnected && !logTimes && (
                <Alert severity="warning" sx={{mx: 1}}>
                    Pipeline timing is disabled on the server.
                </Alert>
            )}

            <Box sx={{px: 1, pb: 0.5}}>
                <FormGroup row sx={{gap: 0.5}}>
                    {(Object.keys(CATEGORY_LABELS) as PipelineTaskCategory[]).map(cat => (
                        <FormControlLabel
                            key={cat}
                            control={
                                <Checkbox
                                    checked={categoryFilters[cat]}
                                    onChange={() => toggleCategory(cat)}
                                    size="small"
                                    sx={{color: CATEGORY_COLORS[cat], '&.Mui-checked': {color: CATEGORY_COLORS[cat]}}}
                                />
                            }
                            label={<Typography variant="caption">{CATEGORY_LABELS[cat]}</Typography>}
                        />
                    ))}
                </FormGroup>
            </Box>

            <Box sx={{flex: 1, minHeight: 0, mx: 1, mb: 1, border: 1, borderColor: 'divider', borderRadius: 1}}>
                <PipelineNetworkTimeline
                    model={model}
                    selectedTaskId={selectedTaskId}
                    onSelectTask={setSelectedTaskId}
                />
            </Box>
        </Box>
    );
}

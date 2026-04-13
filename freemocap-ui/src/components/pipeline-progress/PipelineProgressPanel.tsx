import {useEffect, useRef} from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {selectActivePipelines, pipelineRemoved, PipelinePhase} from '@/store/slices/pipelines';
import PipelineProgressBar from './PipelineProgressBar';

const REMOVAL_DELAY_MS = 3000;

export default function PipelineProgressPanel() {
    const pipelines = useAppSelector(selectActivePipelines);
    const dispatch = useAppDispatch();
    const removalTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

    const entries = Object.values(pipelines);

    // Auto-remove completed/failed pipelines after delay
    useEffect(() => {
        for (const p of entries) {
            const isTerminal = p.phase === PipelinePhase.COMPLETE || p.phase === PipelinePhase.FAILED;
            if (isTerminal && !removalTimers.current[p.pipelineId]) {
                removalTimers.current[p.pipelineId] = setTimeout(() => {
                    dispatch(pipelineRemoved(p.pipelineId));
                    delete removalTimers.current[p.pipelineId];
                }, REMOVAL_DELAY_MS);
            }
        }
        // Clean up timers for pipelines no longer in state
        for (const id of Object.keys(removalTimers.current)) {
            if (!pipelines[id]) {
                clearTimeout(removalTimers.current[id]);
                delete removalTimers.current[id];
            }
        }
    }, [pipelines, dispatch, entries]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            for (const timer of Object.values(removalTimers.current)) {
                clearTimeout(timer);
            }
        };
    }, []);

    if (entries.length === 0) {
        return (
            <Box sx={{height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                <Typography variant="caption" color="text.secondary">
                    No active pipelines
                </Typography>
            </Box>
        );
    }

    return (
        <Box sx={{height: '100%', overflow: 'auto', py: 0.5}}>
            {entries.map((p) => (
                <PipelineProgressBar key={p.pipelineId} pipeline={p}/>
            ))}
        </Box>
    );
}

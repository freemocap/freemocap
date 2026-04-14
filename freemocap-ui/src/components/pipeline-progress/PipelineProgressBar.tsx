import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
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

    return (
        <Box sx={{px: 1, py: 0.5, opacity: isTerminal ? 0.5 : 1}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.25}}>
                <Typography variant="caption" fontWeight="bold" noWrap sx={{flex: 1, mr: 1}}>
                    {pipeline.pipelineType} — {pipeline.pipelineId}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    {isTerminal && pipeline.completedAt
                        ? `${phaseLabel} ${formatTimeAgo(pipeline.completedAt)}`
                        : `${phaseLabel} ${pipeline.progress}%`
                    }
                </Typography>
            </Box>
            <LinearProgress
                variant="determinate"
                value={pipeline.progress}
                color={isFailed ? 'error' : isComplete ? 'success' : 'primary'}
                sx={{height: 6, borderRadius: 1}}
            />
            {pipeline.detail && (
                <Typography variant="caption" color="text.secondary" noWrap sx={{display: 'block', mt: 0.25}}>
                    {pipeline.detail}
                </Typography>
            )}
        </Box>
    );
}

import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import {PipelineProgress, PHASE_LABELS} from '@/store/slices/pipelines';

interface PipelineProgressBarProps {
    pipeline: PipelineProgress;
}

export default function PipelineProgressBar({pipeline}: PipelineProgressBarProps) {
    const phaseLabel = PHASE_LABELS[pipeline.phase] ?? pipeline.phase;
    const isFailed = pipeline.phase === 'failed';
    const isComplete = pipeline.phase === 'complete';

    return (
        <Box sx={{px: 1, py: 0.5}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.25}}>
                <Typography variant="caption" fontWeight="bold" noWrap sx={{flex: 1, mr: 1}}>
                    {pipeline.pipelineType} — {pipeline.pipelineId}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                    {phaseLabel} {pipeline.progress}%
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

import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import {PipelineGroup, PipelinePhase, PipelineProgress} from '@/store/slices/pipelines';

function formatTimeAgo(timestamp: number): string {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
}

function SubProgressBar({pipeline, label}: {pipeline: PipelineProgress; label: string}) {
    const isFailed = pipeline.phase === PipelinePhase.FAILED;
    const isComplete = pipeline.phase === PipelinePhase.COMPLETE;
    const isTerminal = isComplete || isFailed;

    return (
        <Box sx={{mb: 0.5, opacity: isTerminal ? 0.6 : 1}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.125}}>
                <Typography variant="caption" noWrap sx={{flex: 1, mr: 1, color: 'text.secondary', fontSize: '0.68rem'}}>
                    {label}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{fontSize: '0.65rem', flexShrink: 0}}>
                    {isTerminal && pipeline.completedAt
                        ? formatTimeAgo(pipeline.completedAt)
                        : `${pipeline.progress}%`}
                </Typography>
            </Box>
            <LinearProgress
                variant="determinate"
                value={pipeline.progress}
                color={isFailed ? 'error' : isComplete ? 'success' : 'primary'}
                sx={{height: 4, borderRadius: 1}}
            />
        </Box>
    );
}

export default function PipelineGroupCard({group}: {group: PipelineGroup}) {
    const overallProgress =
        group.aggregator?.progress ??
        (group.videoNodes.length > 0
            ? Math.round(group.videoNodes.reduce((sum, n) => sum + n.progress, 0) / group.videoNodes.length)
            : 0);

    const borderColor = group.isFailed ? 'error.main' : group.isComplete ? 'success.main' : 'divider';

    return (
        <Box
            sx={{
                mx: 1,
                my: 0.75,
                p: 1,
                border: 1,
                borderColor,
                borderRadius: 1,
                opacity: group.isActive ? 1 : 0.6,
            }}
        >
            <Box sx={{display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.75}}>
                <Typography variant="caption" fontWeight="bold" noWrap sx={{flex: 1, mr: 1}}>
                    {group.basePipelineId}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{flexShrink: 0}}>
                    {overallProgress}%
                </Typography>
            </Box>

            {group.videoNodes.length > 0 && (
                <Box sx={{pl: 1, borderLeft: 2, borderColor: 'divider', mb: group.aggregator ? 0.75 : 0}}>
                    {group.videoNodes.map((node) => {
                        const videoLabel = node.pipelineId.includes(':')
                            ? node.pipelineId.split(':').slice(1).join(':')
                            : node.pipelineId;
                        return <SubProgressBar key={node.pipelineId} pipeline={node} label={videoLabel}/>;
                    })}
                </Box>
            )}

            {group.aggregator && (
                <Box sx={{mt: 0.5}}>
                    <SubProgressBar pipeline={group.aggregator} label="Aggregation"/>
                </Box>
            )}
        </Box>
    );
}

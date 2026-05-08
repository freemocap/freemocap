import Box from '@mui/material/Box';
import IconButton from '@mui/material/IconButton';
import LinearProgress from '@mui/material/LinearProgress';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import CloseIcon from '@mui/icons-material/Close';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import StopIcon from '@mui/icons-material/Stop';
import {useNavigate} from 'react-router-dom';
import {useAppDispatch} from '@/store/hooks';
import {activeRecordingSet} from '@/store/slices/active-recording/active-recording-slice';
import {useElectronIPC} from '@/services';
import {PipelineGroup, PipelinePhase, PipelineProgress, PHASE_LABELS, PIPELINE_TYPE_CONFIG} from '@/store/slices/pipelines';
import {stopPipeline} from '@/store/slices/pipelines/pipelines-thunks';

function formatTimeAgo(timestamp: number): string {
    const seconds = Math.floor((Date.now() - timestamp) / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    return `${hours}h ago`;
}

function SubProgressBar({pipeline, label, isAggregator = false}: {
    pipeline: PipelineProgress;
    label: string;
    isAggregator?: boolean;
}) {
    const isFailed = pipeline.phase === PipelinePhase.FAILED;
    const isComplete = pipeline.phase === PipelinePhase.COMPLETE;
    const isTerminal = isComplete || isFailed;
    // Aggregator uses indeterminate except when collecting real frame data (SETTING_UP) or at terminal state
    const isIndeterminate = isAggregator && !isTerminal && pipeline.phase !== PipelinePhase.SETTING_UP;

    const rightText = isTerminal && pipeline.completedAt
        ? formatTimeAgo(pipeline.completedAt)
        : isIndeterminate
            ? (pipeline.detail || PHASE_LABELS[pipeline.phase])
            : `${pipeline.progress}%`;

    return (
        <Box sx={{mb: 0.5, opacity: isTerminal ? 0.6 : 1}}>
            <Box sx={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', mb: 0.125}}>
                <Typography variant="caption" noWrap
                            sx={{flex: 1, mr: 1, color: 'text.secondary', fontSize: '0.68rem'}}>
                    {label}
                </Typography>
                <Typography variant="caption" color="text.secondary"
                            sx={{fontSize: '0.65rem', flexShrink: 0, maxWidth: 160}} noWrap>
                    {rightText}
                </Typography>
            </Box>
            <LinearProgress
                variant={isIndeterminate ? 'indeterminate' : 'determinate'}
                value={isIndeterminate ? undefined : pipeline.progress}
                color={isFailed ? 'error' : isComplete ? 'success' : 'primary'}
                sx={{height: 4, borderRadius: 1}}
            />
            {isFailed && pipeline.detail && (
                <Tooltip title={pipeline.detail} placement="bottom" arrow>
                    <Typography
                        variant="caption"
                        color="error"
                        noWrap
                        sx={{display: 'block', fontSize: '0.62rem', mt: 0.25, cursor: 'default'}}
                    >
                        {pipeline.detail}
                    </Typography>
                </Tooltip>
            )}
        </Box>
    );
}

export default function PipelineGroupCard({group, onDismiss}: {
    group: PipelineGroup;
    onDismiss?: () => void;
}) {
    const dispatch = useAppDispatch();
    const navigate = useNavigate();
    const {api} = useElectronIPC();

    const overallProgress =
        group.aggregator?.progress ??
        (group.videoNodes.length > 0
            ? Math.round(group.videoNodes.reduce((sum, n) => sum + n.progress, 0) / group.videoNodes.length)
            : 0);

    const borderColor = group.isFailed ? 'error.main' : group.isComplete ? 'success.main' : 'divider';
    const typeConfig = group.pipelineType ? PIPELINE_TYPE_CONFIG[group.pipelineType] : null;
    const fullPath = group.recordingPath || undefined;
    const recordingName = group.recordingName
    const pipelineId = group.basePipelineId;

    const handleOpenFolder = async () => {
        if (!fullPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({path: fullPath});
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    };

    const handleLoadPlayback = () => {
        if (!group.recordingName) return;
        dispatch(activeRecordingSet({
            recordingName: group.recordingName,
            origin: 'browsed',
        }));
        navigate('/playback');
    };

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
            <Box sx={{display: 'flex', alignItems: 'center', mb: 0.5}}>
                {typeConfig && (
                    <Box sx={{
                        px: 0.75, py: 0.125, mr: 0.75, borderRadius: 1, flexShrink: 0,
                        bgcolor: typeConfig.color + '22',
                        border: `1px solid ${typeConfig.color}66`,
                    }}>
                        <Typography variant="caption" sx={{fontSize: '0.62rem', fontWeight: 600, color: typeConfig.color, lineHeight: 1.4}}>
                            {typeConfig.label}
                        </Typography>
                    </Box>
                )}
                <Typography variant="caption" noWrap sx={{flex: 1, minWidth: 0}}>
                    <Typography component="span" variant="caption" color="text.secondary">Pipeline: </Typography>
                    <Typography component="span" variant="caption" fontWeight="bold">{pipelineId}</Typography>
                </Typography>


                <Typography variant="caption" color="text.secondary" sx={{flexShrink: 0, fontSize: '0.7rem'}}>
                    {overallProgress}%
                </Typography>
                <Tooltip title="Open folder" placement="top">
                    <span>
                        <IconButton size="small" onClick={handleOpenFolder} disabled={!fullPath} sx={{p: 0.25}}>
                            <FolderOpenIcon sx={{fontSize: '0.85rem'}}/>
                        </IconButton>
                    </span>
                </Tooltip>
                <Tooltip title="Load in playback" placement="top">
                    <IconButton size="small" onClick={handleLoadPlayback} sx={{p: 0.25}}>
                        <PlayArrowIcon sx={{fontSize: '0.85rem'}}/>
                    </IconButton>
                </Tooltip>
                {group.isActive && (
                    <Tooltip title="Stop pipeline" placement="top">
                        <IconButton
                            size="small"
                            onClick={() => dispatch(stopPipeline(group.basePipelineId))}
                            sx={{p: 0.25, color: 'error.main'}}
                        >
                            <StopIcon sx={{fontSize: '0.85rem'}}/>
                        </IconButton>
                    </Tooltip>
                )}
                {onDismiss && (
                    <IconButton size="small" onClick={onDismiss} sx={{p: 0.25}}>
                        <CloseIcon sx={{fontSize: '0.75rem'}}/>
                    </IconButton>
                )}
            </Box>
            <Tooltip title={fullPath} placement="top" arrow>
                <Typography variant="caption" noWrap sx={{flex: 1, minWidth: 0}}>
                    <Typography component="span" variant="caption" color="text.secondary">Recording: </Typography>
                    <Typography component="span" variant="caption" fontWeight="bold">{recordingName}</Typography>
                </Typography>
            </Tooltip>
            {group.videoNodes.length > 0 && (
                <Box sx={{pl: 1, borderLeft: 2, borderColor: 'divider', mb: group.aggregator ? 0.75 : 0}}>
                    {group.videoNodes.map((node) => {
                        const cameraId = node.pipelineId.includes(':')
                            ? node.pipelineId.split(':').slice(1).join(':')
                            : node.pipelineId;
                        return <SubProgressBar key={node.pipelineId} pipeline={node} label={`Camera: ${cameraId}`}/>;
                    })}
                </Box>
            )}

            {group.aggregator && (
                <Box sx={{mt: 0.5}}>
                    <SubProgressBar
                        pipeline={group.aggregator}
                        isAggregator={true}
                        label={
                            group.aggregator.phase === PipelinePhase.COMPLETE
                                ? 'Aggregation complete'
                                : group.aggregator.phase === PipelinePhase.FAILED
                                    ? 'Aggregation failed'
                                    : group.videoNodes.length > 0
                                        ? `Aggregating ${group.videoNodes.length} camera${group.videoNodes.length !== 1 ? 's' : ''}`
                                        : PHASE_LABELS[group.aggregator.phase]
                        }
                    />
                </Box>
            )}
        </Box>
    );
}

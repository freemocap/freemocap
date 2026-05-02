import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import TextField from '@mui/material/TextField';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import {useAppDispatch, useAppSelector} from '@/store/hooks';
import {
    selectGroupedPipelines,
    selectHasCompletedPipelines,
    selectShowCompleted,
    selectFilterText,
    toggleShowCompleted,
    filterTextChanged,
} from '@/store/slices/pipelines';
import PipelineGroupCard from './PipelineGroupCard';

export default function PipelineProgressPanel() {
    const groups = useAppSelector(selectGroupedPipelines);
    const hasCompleted = useAppSelector(selectHasCompletedPipelines);
    const showCompleted = useAppSelector(selectShowCompleted);
    const filterText = useAppSelector(selectFilterText);
    const dispatch = useAppDispatch();

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
            <Box sx={{display: 'flex', alignItems: 'center', gap: 1, px: 1, py: 0.5, flexShrink: 0}}>
                <TextField
                    size="small"
                    placeholder="Filter..."
                    value={filterText}
                    onChange={(e) => dispatch(filterTextChanged(e.target.value))}
                    sx={{
                        flex: 1,
                        '& .MuiInputBase-root': {height: 28, fontSize: '0.75rem'},
                    }}
                />
                {hasCompleted && (
                    <FormControlLabel
                        control={
                            <Checkbox
                                size="small"
                                checked={showCompleted}
                                onChange={() => dispatch(toggleShowCompleted())}
                                sx={{p: 0.25}}
                            />
                        }
                        label={<Typography variant="caption">Show completed</Typography>}
                        sx={{mr: 0, ml: 0}}
                    />
                )}
            </Box>

            <Box sx={{flex: 1, overflow: 'auto'}}>
                {groups.length === 0 ? (
                    <Box sx={{height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
                        <Typography variant="caption" color="text.secondary">
                            No active pipelines
                        </Typography>
                    </Box>
                ) : (
                    groups.map((group) => (
                        <PipelineGroupCard key={group.basePipelineId} group={group}/>
                    ))
                )}
            </Box>
        </Box>
    );
}

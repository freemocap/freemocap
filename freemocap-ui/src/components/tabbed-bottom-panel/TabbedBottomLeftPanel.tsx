import Box from '@mui/material/Box';
import FramerateViewerPanel from '@/components/framerate-viewer/FrameRateViewer';
import PipelineProgressPanel from '@/components/pipeline-progress/PipelineProgressPanel';
import {TabbedContent} from '@/components/ui-components/TabbedContent';
import {useAppSelector} from '@/store/hooks';
import {selectActiveBasePipelineCount} from '@/store/slices/pipelines';

function PipelineTabLabel() {
    const activeCount = useAppSelector(selectActiveBasePipelineCount);
    return (
        <Box sx={{display: 'flex', alignItems: 'center', gap: 0.75}}>
            Pipelines
            {activeCount > 0 && (
                <Box
                    sx={{
                        width: 7,
                        height: 7,
                        borderRadius: '50%',
                        bgcolor: 'primary.main',
                        flexShrink: 0,
                        animation: 'fmcPulse 1.4s ease-in-out infinite',
                        '@keyframes fmcPulse': {
                            '0%, 100%': {opacity: 1, transform: 'scale(1)'},
                            '50%': {opacity: 0.3, transform: 'scale(0.7)'},
                        },
                    }}
                />
            )}
        </Box>
    );
}

export default function TabbedBottomLeftPanel({isCollapsed = false}: { isCollapsed?: boolean }) {
    if (isCollapsed) {
        return <FramerateViewerPanel isCollapsed={true}/>;
    }
    return (
        <TabbedContent tabs={[
            {label: 'Framerate', content: <FramerateViewerPanel/>},
            // {label: <PipelineTabLabel/>, content: <PipelineProgressPanel/>},
        ]}/>
    );
}

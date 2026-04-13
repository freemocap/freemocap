import {useState} from 'react';
import Box from '@mui/material/Box';
import Tabs from '@mui/material/Tabs';
import Tab from '@mui/material/Tab';
import FramerateViewerPanel from '@/components/framerate-viewer/FrameRateViewer';
import PipelineProgressPanel from '@/components/pipeline-progress/PipelineProgressPanel';

export default function TabbedBottomLeftPanel() {
    const [tab, setTab] = useState(0);

    return (
        <Box sx={{height: '100%', display: 'flex', flexDirection: 'column'}}>
            <Tabs
                value={tab}
                onChange={(_, v) => setTab(v)}
                sx={{minHeight: 28, '& .MuiTab-root': {minHeight: 28, py: 0, fontSize: '0.75rem'}}}
            >
                <Tab label="Framerate"/>
                <Tab label="Pipelines"/>
            </Tabs>
            {/* Keep both mounted so framerate charts don't reset */}
            <Box sx={{flex: 1, overflow: 'hidden', display: tab === 0 ? 'block' : 'none'}}>
                <FramerateViewerPanel/>
            </Box>
            <Box sx={{flex: 1, overflow: 'hidden', display: tab === 1 ? 'block' : 'none'}}>
                <PipelineProgressPanel/>
            </Box>
        </Box>
    );
}

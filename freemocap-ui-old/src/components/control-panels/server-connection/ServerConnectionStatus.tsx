import React from 'react';
import {Box, Collapse} from '@mui/material';
import {useServerPanel} from './useServerPanel';
import {ServerStatusBar} from './ServerStatusBar';
import {ServerProcessSection} from './ServerProcessSection';
import {WebSocketSection} from './WebSocketSection';

export const ServerConnectionStatus: React.FC = () => {
    const panel = useServerPanel();
    const {theme, expanded, setExpanded, isElectron} = panel;

    return (
        <Box
            sx={{
                borderBottom: `1px solid ${theme.palette.divider}`,
                backgroundColor: theme.palette.mode === 'dark'
                    ? 'rgba(0, 0, 0, 0.2)'
                    : 'rgba(0, 0, 0, 0.02)',
            }}
        >
            <ServerStatusBar {...panel} setExpanded={setExpanded} expanded={expanded}/>

            <Collapse in={expanded}>
                <Box sx={{px: 1.5, pb: 1.5, display: 'flex', flexDirection: 'column', gap: 1.5}}>
                    {isElectron && <ServerProcessSection {...panel}/>}
                    <WebSocketSection {...panel}/>
                </Box>
            </Collapse>
        </Box>
    );
};

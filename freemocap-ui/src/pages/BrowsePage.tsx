import React from 'react';
import {Box, useTheme} from '@mui/material';
import {useNavigate} from 'react-router-dom';
import {Footer} from '@/components/ui-components/Footer';
import ErrorBoundary from '@/components/common/ErrorBoundary';
import {RecordingBrowser} from '@/components/playback/RecordingBrowser';
import {usePlaybackContext} from '@/components/playback/PlaybackContext';

const BrowsePage: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const ctx = usePlaybackContext();

    return (
        <Box
            sx={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider,
            }}
        >
            <Box sx={{flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
                <ErrorBoundary>
                    <RecordingBrowser
                        activeRecordingPath={ctx?.recordingPath ?? null}
                        onRecordingLoaded={(videos, recPath, recFps) => {
                            ctx?.onRecordingLoaded(videos, recPath, recFps);
                            navigate('/playback');
                        }}
                    />
                </ErrorBoundary>
            </Box>
            <Box component="footer" sx={{p: 0.5}}>
                <Footer/>
            </Box>
        </Box>
    );
};

export default BrowsePage;

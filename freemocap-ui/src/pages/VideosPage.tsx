import React from 'react';
import Box from "@mui/material/Box";
import ErrorBoundary from "@/components/common/ErrorBoundary";
import {Footer} from "@/components/ui-components/Footer";
import {useTheme} from "@mui/material/styles";
import {Typography} from '@mui/material';
import {useTranslation} from "react-i18next";

const VideosPage: React.FC = () => {
    const theme = useTheme();
    const {t} = useTranslation();

    return (
        <React.Fragment>
            <Box sx={{
                py: 1,
                px: 1,
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.background.paper,
                borderStyle: 'solid',
                borderWidth: '1px',
                borderColor: theme.palette.divider
            }}>
                <Box sx={{
                    flex: 1,
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'center',
                    alignItems: 'center',
                    overflow: 'hidden',
                }}>
                    <ErrorBoundary>
                        <Typography variant="h4" gutterBottom>
                            {t('loadSynchronizedVideos')}
                        </Typography>
                        <Typography variant="body1">
                            {t('loadSynchronizedVideosDescription')}
                        </Typography>
                    </ErrorBoundary>
                </Box>
                <Box component="footer" sx={{p: 1}}>
                    <Footer/>
                </Box>
            </Box>
        </React.Fragment>
    );
};

export default VideosPage;

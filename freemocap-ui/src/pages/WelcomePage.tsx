import React, {useEffect, useState, useRef} from 'react';
import {Box, Container, Fade, Grow, Paper, Typography} from '@mui/material';
import {useNavigate} from 'react-router-dom';
import {useTheme} from '@mui/material/styles';
import {Footer} from '@/components/ui-components/Footer';
import {useElectronIPC} from "@/services";
import {useServer} from "@/services/server/ServerContextProvider"; // Adjust import path as needed

const WelcomePage: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();

    // Track previous camera count to detect 0 -> >0 transition
    const prevCountRef = useRef(connectedCameraIds.length);

    useEffect(() => {
        const prevCount = prevCountRef.current;
        const currentCount = connectedCameraIds.length;

        // Auto-navigate to cameras page only when first camera connects (0 -> >0 transition)
        if (prevCount === 0 && currentCount > 0) {
            navigate('/cameras');
        }

        prevCountRef.current = currentCount;
    }, [connectedCameraIds, navigate]);

    useEffect(() => {
        const fetchLogo = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    // Use the new base64 method that returns a data URL
                    const dataUrl = await api.assets.getLogoBase64.query();
                    if (dataUrl) {
                        setLogoDataUrl(dataUrl);
                    } else {
                        console.warn('Logo image not found...');
                    }
                }
            } catch (error) {
                console.error('Failed to load logo:', error);

            }
        };

        fetchLogo();
    }, [isElectron, api]);

    return (
        <Container maxWidth="md" sx={{
            height: '100%',
            width: '100%',
            bgcolor: theme.palette.background.default,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            py: 4
        }}>
            <Fade in={true} timeout={800}>
                <Paper
                    elevation={6}
                    sx={{
                        p: {xs: 3, sm: 5},
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        width: '100%',
                        backgroundColor: theme.palette.background.paper,
                        mx: 'auto',
                        borderRadius: 3,
                        boxShadow: theme.palette.mode === 'dark'
                            ? '0 8px 32px rgba(0, 0, 0, 0.5)'
                            : '0 8px 32px rgba(0, 0, 0, 0.1)',
                        overflow: 'hidden',
                        position: 'relative'
                    }}
                >
                    {/* Background accent */}
                    <Box sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '8px',
                        background: `linear-gradient(90deg, ${theme.palette.primary.main}, ${theme.palette.secondary.main})`,
                    }}/>

                    <Grow in={true} timeout={1000}>
                        <Box
                            sx={{
                                width: 240,
                                height: 240,
                                mb: 4,
                                mt: 2,
                                display: 'flex',
                                justifyContent: 'center',
                                alignItems: 'center',
                                transition: 'transform 0.3s ease-in-out',
                                '&:hover': {
                                    transform: 'scale(1.05)'
                                }
                            }}
                        >
                            {logoDataUrl && (
                                <img
                                    src={logoDataUrl}
                                    alt="FreeMoCap Logo"
                                    style={{
                                        maxWidth: '100%',
                                        maxHeight: '100%',
                                        objectFit: 'contain',
                                        filter: theme.palette.mode === 'dark'
                                            ? 'drop-shadow(0 0 10px rgba(255,255,255,0.2))'
                                            : 'drop-shadow(0 0 10px rgba(0,0,0,0.1))'
                                    }}
                                />
                            )}
                        </Box>
                    </Grow>

                    <Typography
                        variant="h3"
                        component="h1"
                        gutterBottom
                        sx={{
                            fontWeight: 'bold',
                            textAlign: 'center',
                            background: theme.palette.text.primary,
                            WebkitBackgroundClip: 'text',
                            WebkitTextFillColor: 'transparent',
                            backgroundClip: 'text',
                            textFillColor: 'transparent',
                            mb: 2
                        }}
                    >
                        Welcome to FreeMoCap
                    </Typography>

                    <Typography
                        variant="subtitle1"
                        color="text.secondary"
                        sx={{
                            mb: 5,
                            textAlign: 'center',
                            maxWidth: '80%',
                            fontSize: '1.1rem'
                        }}
                    >
                        Record and View Synchronized Videos
                    </Typography>

                    <Box component="footer" sx={{p: 3}}>
                        <Footer/>
                    </Box>
                </Paper>
            </Fade>
        </Container>
    );
};

export default WelcomePage;

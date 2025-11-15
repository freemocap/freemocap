import React, {useEffect, useRef, useState} from 'react';
import {
    Box,
    Button,
    CircularProgress,
    Container,
    darken,
    Fade,
    Grow,
    Link as MuiLink,
    Paper,
    Typography
} from '@mui/material';
import {useNavigate} from 'react-router-dom';
import {useTheme} from '@mui/material/styles';
import VideocamIcon from '@mui/icons-material/Videocam';
import {Footer} from '@/components/ui-components/Footer';
import {useElectronIPC} from "@/services";
import {connectRealtimePipeline, useAppDispatch} from "@/store";
import {useServer} from "@/hooks/useServer";

const WelcomePage: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const dispatch = useAppDispatch();
    const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
    const [isConnecting, setIsConnecting] = useState<boolean>(false);
    const { isElectron, api } = useElectronIPC();
    const { connectedCameraIds } = useServer();

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

    const handleConnectCameras = async (): Promise<void> => {
        setIsConnecting(true);
        try {
            await dispatch(connectRealtimePipeline()).unwrap();
            // Navigation will happen automatically via the useEffect above
        } catch (error) {
            console.error('Error connecting to cameras:', error);
            setIsConnecting(false);
        }
    };

    return (
        <Container maxWidth="md" sx={{
            height: '100%',
            width: '100%',
            bgcolor: theme.palette.background.default,
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            alignItems: 'center',
            py: 4,
            gap: 3
        }}>
            <Fade in={true} timeout={800}>
                <Paper
                    elevation={6}
                    sx={{
                        p: { xs: 3, sm: 5 },
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
                        position: 'relative',
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
                    }} />

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
                            mb: 2
                        }}
                    >
                        Welcome to FreeMoCap
                    </Typography>

                    <Typography
                        variant="subtitle1"
                        color="text.secondary"
                        sx={{
                            mb: 4,
                            textAlign: 'center',
                            maxWidth: '80%',
                            fontSize: '1.1rem'
                        }}
                    >
                        Free and open source markerless motion capture for everyone.
                    </Typography>

                    <Button
                        variant="contained"
                        size="large"
                        onClick={handleConnectCameras}
                        disabled={isConnecting}
                        startIcon={isConnecting ? <CircularProgress size={20} color="inherit" /> : <VideocamIcon />}
                        sx={{
                            mb: 3,
                            py: 2,
                            px: 6,
                            fontSize: '1.2rem',
                            fontWeight: 'bold',
                            borderRadius: 3,
                            textTransform: 'none',
                            boxShadow: theme.palette.mode === 'dark'
                                ? '0 4px 20px rgba(0, 0, 0, 0.5)'
                                : '0 4px 20px rgba(0, 0, 0, 0.15)',
                            // background: `linear-gradient(135deg, ${theme.palette.primary.main}, ${darken(theme.palette.secondary.main, 0.25)})`,
                            background: darken(theme.palette.secondary.main, 0.25),
                            transition: 'all 0.3s ease-in-out',
                            '&:hover': {
                                transform: 'translateY(-2px)',
                                boxShadow: theme.palette.mode === 'dark'
                                    ? '0 6px 24px rgba(0, 0, 0, 0.6)'
                                    : '0 6px 24px rgba(0, 0, 0, 0.2)',
                            },
                            '&:disabled': {
                                background: theme.palette.action.disabledBackground,
                            }
                        }}
                    >
                        {isConnecting ? 'Connecting...' : 'Connect Cameras'}
                    </Button>

                    <Box component="footer" sx={{ p: 3, mt: 2 }}>
                        <Footer />
                    </Box>
                </Paper>
            </Fade>

            {/* Research Tool Disclaimer - Outside main clickable area */}
            <Paper
                elevation={1}
                sx={{
                    p: 2.5,
                    width: '100%',
                    backgroundColor: theme.palette.mode === 'dark'
                        ? 'rgba(255, 255, 255, 0.03)'
                        : 'rgba(0, 0, 0, 0.02)',
                    borderRadius: 2,
                }}
            >
                <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                        fontSize: '0.85rem',
                        lineHeight: 1.8,
                        '& a': {
                            color: theme.palette.mode === 'dark'
                                ? theme.palette.primary.light
                                : theme.palette.primary.main,
                            textDecoration: 'none',
                            fontWeight: 500,
                            transition: 'all 0.2s',
                            '&:hover': {
                                textDecoration: 'underline',
                                color: theme.palette.mode === 'dark'
                                    ? theme.palette.primary.main
                                    : theme.palette.primary.dark
                            }
                        }
                    }}
                >
                    FreeMoCap is currently a research and educational tool, not cleared by the FDA for clinical use. Motion capture devices are regulated under{' '}
                    <MuiLink
                        href="https://www.ecfr.gov/current/title-21/chapter-I/subchapter-H/part-890"
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                        21 CFR Part 890 (Physical Medicine Devices)
                    </MuiLink>
                    {' '}and require{' '}
                    <MuiLink
                        href="https://www.fda.gov/medical-devices/premarket-submissions-selecting-and-preparing-correct-submission/premarket-notification-510k"
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                        510(k) clearance
                    </MuiLink>
                    {' '}for clinical applications.
                    <br />
                    <br />
                    <MuiLink
                        href="https://freemocap.github.io/documentation/validation/"
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                        - View our validation studies
                    </MuiLink>
                    <br />
                    <MuiLink
                        href="https://freemocap.github.io/documentation/community/fda_pathway/"
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e: React.MouseEvent) => e.stopPropagation()}
                    >
                        - Join our journey towards FDA certification
                    </MuiLink>
                </Typography>
            </Paper>
        </Container>
    );
};

export default WelcomePage;

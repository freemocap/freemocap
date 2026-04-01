import React, {useEffect, useState, useRef, useCallback} from 'react';
import {
    Box, Button, Checkbox, CircularProgress, Container,
    darken, Divider, Fade, FormControlLabel, Grow, Paper, Stack, Typography
} from '@mui/material';
import {useNavigate} from 'react-router-dom';
import {useTheme} from '@mui/material/styles';
import VideocamIcon from '@mui/icons-material/Videocam';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import {Footer} from '@/components/ui-components/Footer';
import {useElectronIPC} from "@/services";
import {useServer} from "@/services/server/ServerContextProvider";
import {useTranslation} from "react-i18next";
import {LanguageSwitcher} from "@/components/languages/LanguageSwitcher";
import {VersionChip} from "@/components/ui-components/VersionChip";
import {useAppDispatch} from "@/store";
import {camerasConnectOrUpdate} from "@/store/slices/cameras/cameras-thunks";
import {EXTERNAL_URLS} from "@/constants/external-urls";

const WelcomePage: React.FC = () => {
    const {t} = useTranslation();
    const theme = useTheme();
    const navigate = useNavigate();
    const [logoDataUrl, setLogoDataUrl] = useState<string | null>(null);
    const [telemetryEnabled, setTelemetryEnabled] = useState<boolean>(true);
    const [telemetryLoaded, setTelemetryLoaded] = useState<boolean>(false);
    const {isElectron, api} = useElectronIPC();
    const {connectedCameraIds} = useServer();
    const dispatch = useAppDispatch();
    const [isConnecting, setIsConnecting] = useState(false);

    // Track previous camera count to detect 0 -> >0 transition
    const prevCountRef = useRef(connectedCameraIds.length);

    useEffect(() => {
        const prevCount = prevCountRef.current;
        const currentCount = connectedCameraIds.length;

        // Auto-navigate to cameras page when first camera connects (0 -> >0 transition)
        if (prevCount === 0 && currentCount > 0) {
            navigate('/cameras');
        }

        prevCountRef.current = currentCount;
    }, [connectedCameraIds, navigate]);

    useEffect(() => {
        const fetchLogo = async (): Promise<void> => {
            try {
                if (isElectron && api) {
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

    // Load telemetry preference on mount
    useEffect(() => {
        const loadTelemetryPref = async (): Promise<void> => {
            try {
                if (isElectron && api) {
                    const enabled = await api.telemetry.getEnabled.query();
                    setTelemetryEnabled(enabled);
                }
            } catch (error) {
                console.error('Failed to load telemetry preference:', error);
            } finally {
                setTelemetryLoaded(true);
            }
        };

        loadTelemetryPref();
    }, [isElectron, api]);

    const handleTelemetryToggle = useCallback(async (_event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => {
        setTelemetryEnabled(checked);
        try {
            if (isElectron && api) {
                await api.telemetry.setEnabled.mutate({enabled: checked});
            }
        } catch (error) {
            console.error('Failed to save telemetry preference:', error);
        }
    }, [isElectron, api]);

    const handleConnectCameras = useCallback(async () => {
        setIsConnecting(true);
        try {
            await dispatch(camerasConnectOrUpdate()).unwrap();
        } catch (error) {
            console.error('Error connecting cameras:', error);
        } finally {
            setIsConnecting(false);
        }
    }, [dispatch]);

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
                    {/* Gradient accent bar */}
                    <Box sx={{
                        position: 'absolute',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '8px',
                        background: `linear-gradient(90deg, ${theme.palette.primary.light}, ${theme.palette.info.main})`,
                    }}/>

                    {/* ── HERO SECTION ── */}
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 2 }}>
                        <Grow in={true} timeout={1000}>
                            <Box
                                sx={{
                                    width: 180,
                                    height: 180,
                                    mb: 2,
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
                                mb: 1
                            }}
                        >
                            {t('welcomeTitle')}
                        </Typography>

                        <Typography
                            variant="subtitle1"
                            color="text.secondary"
                            sx={{
                                mb: 1,
                                textAlign: 'center',
                                maxWidth: '80%',
                                fontSize: '1.1rem'
                            }}
                        >
                            {t('welcomeSubtitle')}
                        </Typography>
                    </Box>

                    {/* ── PRIMARY CTA ── */}
                    <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center', mb: 2 }}>
                        <Button
                            variant="contained"
                            size="large"
                            startIcon={isConnecting
                                ? <CircularProgress size={24} color="inherit" />
                                : <VideocamIcon sx={{ fontSize: 28 }} />
                            }
                            onClick={handleConnectCameras}
                            disabled={isConnecting}
                            sx={{
                                '&&': {
                                    px: 6,
                                    py: 2,
                                    fontSize: '1.25rem',
                                    fontWeight: 600,
                                    minHeight: 56,
                                    padding: '16px 48px',
                                },
                                width: '100%',
                                maxWidth: 400,
                                borderRadius: 3,
                                textTransform: 'none',
                                background: darken(theme.palette.info.dark, .4),
                                color: theme.palette.text.primary,
                                border: `4px solid ${theme.palette.secondary.main}`,
                                boxShadow: `0 4px 20px rgba(245, 0, 87, 0.25)`,
                                '&:hover': {
                                background: theme.palette.info.dark,
                                    boxShadow: `0 6px 28px rgba(245, 0, 87, 0.4)`,
                                    transform: 'translateY(-1px)',
                                    border: `4px solid ${theme.palette.secondary.light}`,
                                    color: theme.palette.text.primary,
                                },
                                transition: 'all 0.2s ease-in-out',
                            }}
                        >
                            {t('connectToCameras')}
                        </Button>
                    </Box>

                    {/* ── SECONDARY LINKS ── */}
                    <Stack direction="row" spacing={2} sx={{ mb: 2 }}>
                        <Button
                            variant="text"
                            size="small"
                            color="inherit"
                            endIcon={<OpenInNewIcon sx={{fontSize: 14}} />}
                            onClick={() => window.open(EXTERNAL_URLS.DOCS, '_blank')}
                            sx={{
                                textTransform: 'none',
                                color: theme.palette.info.light,
                                '&:hover': { color: theme.palette.info.main },
                            }}
                        >
                            {t('documentation')}
                        </Button>
                        <Button
                            variant="text"
                            size="small"
                            color="inherit"
                            endIcon={<OpenInNewIcon sx={{fontSize: 14}} />}
                            onClick={() => window.open(EXTERNAL_URLS.ROADMAP, '_blank')}
                            sx={{
                                textTransform: 'none',
                                color: theme.palette.info.light,
                                '&:hover': { color: theme.palette.info.main },
                            }}
                        >
                            {t('roadmap')}
                        </Button>
                    </Stack>

                    {/* ── SETTINGS AREA ── */}
                    <Divider sx={{ width: '60%', my: 1.5 }} />
                    <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, mb: 2 }}>
                        <LanguageSwitcher/>
                        {telemetryLoaded && (
                            <Fade in={true} timeout={600}>
                                <FormControlLabel
                                    control={
                                        <Checkbox
                                            checked={telemetryEnabled}
                                            onChange={handleTelemetryToggle}
                                            size="small"
                                        />
                                    }
                                    label={
                                        <Typography variant="body2" color="text.secondary">
                                            {t('sendAnonymousPings')}
                                        </Typography>
                                    }
                                />
                            </Fade>
                        )}
                        <VersionChip variant="compact" />
                    </Box>

                    {/* ── FOOTER ── */}
                    <Box sx={{ textAlign: 'center' }}>
                        <Footer/>
                    </Box>
                </Paper>
            </Fade>
        </Container>
    );
};

export default WelcomePage;

import React, {useCallback, useEffect, useRef, useState} from 'react';
import {
    Box,
    Button,
    Checkbox,
    CircularProgress,
    Container,
    darken,
    Divider,
    Fade,
    FormControlLabel,
    Grow,
    Link as MuiLink,
    Paper,
    Stack,
    Typography
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
            navigate('/streaming');
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
        <Box sx={{
            width: '100%',
            height: '100%',
            bgcolor: theme.palette.background.default,
            display: 'flex',
            flexDirection: 'column',
            overflowY: 'auto',
            overflowX: 'hidden',
        }}>
            <Container maxWidth="md" sx={{
                py: 4,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                flex: '0 0 auto',
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
                        <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'center', mb: 2}}>
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
                        <Box sx={{width: '100%', display: 'flex', justifyContent: 'center', mb: 2}}>
                            <Button
                                variant="contained"
                                size="large"
                                startIcon={isConnecting
                                    ? <CircularProgress size={24} color="inherit"/>
                                    : <VideocamIcon sx={{fontSize: 28}}/>
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


                        {/* ── SETTINGS AREA ── */}
                        <Divider sx={{width: '60%', my: 1.5}}/>
                        <Box sx={{display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1, mb: 2}}>
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
                            <VersionChip variant="compact"/>
                        </Box>

                        {/* ── SECONDARY LINKS ── */}
                        <Stack direction="row" spacing={2} sx={{mb: 2}}>
                            <Button
                                variant="text"
                                size="small"
                                color="inherit"
                                endIcon={<OpenInNewIcon sx={{fontSize: 14}}/>}
                                onClick={() => window.open(EXTERNAL_URLS.DOCS, '_blank')}
                                sx={{
                                    textTransform: 'none',
                                    color: theme.palette.info.light,
                                    '&:hover': {color: theme.palette.info.main},
                                }}
                            >
                                {t('documentation')}
                            </Button>
                            <Button
                                variant="text"
                                size="small"
                                color="inherit"
                                endIcon={<OpenInNewIcon sx={{fontSize: 14}}/>}
                                onClick={() => window.open(EXTERNAL_URLS.ROADMAP, '_blank')}
                                sx={{
                                    textTransform: 'none',
                                    color: theme.palette.info.light,
                                    '&:hover': {color: theme.palette.info.main},
                                }}
                            >
                                {t('roadmap')}
                            </Button>
                        </Stack>

                        {/* ── FOOTER ── */}
                        <Box sx={{textAlign: 'center'}}>
                            <Footer/>
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
                        mt: 2,
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
                        FreeMoCap is not cleared by the FDA for clinical use and should to be used in clinical diagnosis and treatment.
                        Motion capture devices are regulated under{' '}
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
                        <br/>
                        <br/>
                        <MuiLink
                            href="https://aaroncherian.github.io/freemocap_validation/"
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e: React.MouseEvent) => e.stopPropagation()}
                        >
                            - View our validation studies
                        </MuiLink>
                        <br/>
                        <MuiLink
                            href="https://github.com/freemocap/freemocap_foundation/issues/32"
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e: React.MouseEvent) => e.stopPropagation()}
                        >
                            - Join our journey towards FDA certification
                        </MuiLink>
                    </Typography>
                </Paper>
            </Container>
        </Box>
    );
};

export default WelcomePage;

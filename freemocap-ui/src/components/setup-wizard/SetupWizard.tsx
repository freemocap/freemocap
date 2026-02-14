import React, { useState, useEffect, useCallback } from 'react';
import {
    Box,
    Typography,
    Button,
    LinearProgress,
    CircularProgress,
    Chip,
    Tooltip,
    Alert,
    Paper,
    Stepper,
    Step,
    StepLabel,
    IconButton,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import ComputerIcon from '@mui/icons-material/Computer';
import MemoryIcon from '@mui/icons-material/Memory';
import StorageIcon from '@mui/icons-material/Storage';
import SpeedIcon from '@mui/icons-material/Speed';
import VideocamIcon from '@mui/icons-material/Videocam';
import ArrowForwardIcon from '@mui/icons-material/ArrowForward';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CloseIcon from '@mui/icons-material/Close';
import { useElectronIPC } from '@/services';

// ── Types (mirrors electron-side types) ──

interface CpuInfo { model: string; cores: number; threads: number; speedMhz: number }
interface RamInfo { totalGb: number; availableGb: number }
interface GpuInfo { name: string; vendor: string; vramMb: number | null; cudaAvailable: boolean; cudaVersion: string | null }
interface DiskInfo { path: string; totalGb: number; freeGb: number }
interface OsInfo { platform: string; release: string; arch: string; hostname: string }
type PerformanceTier = 'basic' | 'standard' | 'advanced' | 'pro';
interface PerformanceRecommendation {
    tier: PerformanceTier;
    label: string;
    description: string;
    maxCameras: number;
    maxResolution: string;
    realtimeTracking: boolean;
    warnings: string[];
}
interface SystemScanResult {
    cpu: CpuInfo;
    ram: RamInfo;
    gpus: GpuInfo[];
    disk: DiskInfo;
    os: OsInfo;
    recommendation: PerformanceRecommendation;
    scannedAt: string;
}

type DependencyStatus = 'installed' | 'missing' | 'outdated' | 'checking' | 'installing' | 'error';
interface DependencyInfo {
    id: string;
    name: string;
    description: string;
    required: boolean;
    status: DependencyStatus;
    version: string | null;
    installedPath: string | null;
    error: string | null;
}

// ── Constants ──

const SETUP_COMPLETE_KEY = 'setupComplete';
const SYSTEM_SCAN_KEY = 'lastSystemScan';
const STEPS = ['System Scan', 'Dependencies', 'Ready'];

const TIER_COLORS: Record<PerformanceTier, string> = {
    basic: '#ff9800',
    standard: '#2196f3',
    advanced: '#4caf50',
    pro: '#00e5ff',
};

const TIER_EMOJIS: Record<PerformanceTier, string> = {
    basic: '🐢',
    standard: '🏃',
    advanced: '🚀',
    pro: '⚡',
};

// ── Status icon helper ──

function StatusIcon({ status }: { status: DependencyStatus }) {
    switch (status) {
        case 'installed':
            return <CheckCircleIcon sx={{ color: '#4caf50', fontSize: 20 }} />;
        case 'missing':
            return <ErrorIcon sx={{ color: '#f44336', fontSize: 20 }} />;
        case 'outdated':
            return <WarningIcon sx={{ color: '#ff9800', fontSize: 20 }} />;
        case 'checking':
        case 'installing':
            return <CircularProgress size={18} />;
        case 'error':
            return <ErrorIcon sx={{ color: '#f44336', fontSize: 20 }} />;
    }
}

// ── Step 0: System Scan ──

function SystemScanStep({
    scanResult,
    scanning,
    onRescan,
}: {
    scanResult: SystemScanResult | null;
    scanning: boolean;
    onRescan: () => void;
}) {
    const theme = useTheme();

    if (scanning) {
        return (
            <Box sx={{ textAlign: 'center', py: 6 }}>
                <CircularProgress size={48} />
                <Typography sx={{ mt: 2, color: theme.palette.text.secondary }}>
                    Scanning your system...
                </Typography>
            </Box>
        );
    }

    if (!scanResult) {
        return (
            <Box sx={{ textAlign: 'center', py: 6 }}>
                <Typography color="error">Scan failed. Please retry.</Typography>
                <Button onClick={onRescan} startIcon={<RefreshIcon />} sx={{ mt: 2 }}>
                    Retry Scan
                </Button>
            </Box>
        );
    }

    const { cpu, ram, gpus, disk, os: osInfo, recommendation } = scanResult;
    const tierColor = TIER_COLORS[recommendation.tier];

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Performance Tier Badge */}
            <Paper
                elevation={0}
                sx={{
                    p: 2,
                    border: `2px solid ${tierColor}`,
                    borderRadius: 2,
                    background: `${tierColor}11`,
                    textAlign: 'center',
                }}
            >
                <Typography variant="h5" sx={{ fontWeight: 700, color: tierColor }}>
                    {TIER_EMOJIS[recommendation.tier]} {recommendation.label} System
                </Typography>
                <Typography variant="body2" sx={{ mt: 0.5, color: theme.palette.text.secondary }}>
                    {recommendation.description}
                </Typography>
                <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, mt: 1.5, flexWrap: 'wrap' }}>
                    <Chip
                        icon={<VideocamIcon />}
                        label={`Up to ${recommendation.maxCameras} cameras`}
                        size="small"
                        sx={{ borderColor: tierColor, color: tierColor }}
                        variant="outlined"
                    />
                    <Chip
                        label={`${recommendation.maxResolution} max`}
                        size="small"
                        sx={{ borderColor: tierColor, color: tierColor }}
                        variant="outlined"
                    />
                    {recommendation.realtimeTracking && (
                        <Chip
                            icon={<SpeedIcon />}
                            label="Real-time tracking"
                            size="small"
                            sx={{ borderColor: tierColor, color: tierColor }}
                            variant="outlined"
                        />
                    )}
                </Box>
            </Paper>

            {/* Hardware Details Grid */}
            <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5 }}>
                {/* CPU */}
                <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <MemoryIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                        <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>
                            CPU
                        </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>
                        {cpu.model}
                    </Typography>
                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                        {cpu.threads} threads • {cpu.cores} cores • {cpu.speedMhz} MHz
                    </Typography>
                </Paper>

                {/* RAM */}
                <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <ComputerIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                        <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>
                            MEMORY
                        </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {ram.totalGb} GB total
                    </Typography>
                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                        {ram.availableGb} GB available
                    </Typography>
                </Paper>

                {/* GPU */}
                <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <SpeedIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                        <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>
                            GPU
                        </Typography>
                    </Box>
                    {gpus.length > 0 ? gpus.map((gpu, i) => (
                        <Box key={i}>
                            <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>
                                {gpu.name}
                            </Typography>
                            <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                {gpu.vramMb ? `${Math.round(gpu.vramMb / 1024)} GB VRAM` : 'VRAM unknown'}
                                {gpu.cudaAvailable ? ` • CUDA ${gpu.cudaVersion || '✓'}` : ''}
                            </Typography>
                        </Box>
                    )) : (
                        <Typography variant="body2" sx={{ color: theme.palette.text.disabled }}>
                            No dedicated GPU detected
                        </Typography>
                    )}
                </Paper>

                {/* Disk */}
                <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <StorageIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                        <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>
                            DISK
                        </Typography>
                    </Box>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                        {disk.freeGb} GB free
                    </Typography>
                    <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                        of {disk.totalGb} GB total
                    </Typography>
                    {disk.freeGb > 0 && disk.freeGb < 20 && (
                        <LinearProgress
                            variant="determinate"
                            value={((disk.totalGb - disk.freeGb) / disk.totalGb) * 100}
                            color="warning"
                            sx={{ mt: 0.5, height: 4, borderRadius: 1 }}
                        />
                    )}
                </Paper>
            </Box>

            {/* Warnings */}
            {recommendation.warnings.length > 0 && (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                    {recommendation.warnings.map((w, i) => (
                        <Alert key={i} severity="warning" sx={{ py: 0, fontSize: '0.75rem' }}>
                            {w}
                        </Alert>
                    ))}
                </Box>
            )}

            {/* Rescan button */}
            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Button size="small" startIcon={<RefreshIcon />} onClick={onRescan}>
                    Rescan
                </Button>
            </Box>
        </Box>
    );
}

// ── Step 1: Dependencies ──

function DependenciesStep({
    dependencies,
    installing,
    onInstall,
    onRefresh,
}: {
    dependencies: DependencyInfo[];
    installing: string | null;
    onInstall: (id: string) => void;
    onRefresh: () => void;
}) {
    const theme = useTheme();

    if (dependencies.length === 0) {
        return (
            <Box sx={{ textAlign: 'center', py: 6 }}>
                <CircularProgress size={48} />
                <Typography sx={{ mt: 2, color: theme.palette.text.secondary }}>
                    Checking dependencies...
                </Typography>
            </Box>
        );
    }

    const required = dependencies.filter(d => d.required);
    const optional = dependencies.filter(d => !d.required);

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* Required */}
            <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, color: theme.palette.text.secondary, fontWeight: 600 }}>
                    REQUIRED
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {required.map(dep => (
                        <DependencyRow
                            key={dep.id}
                            dep={dep}
                            installing={installing === dep.id}
                            onInstall={() => onInstall(dep.id)}
                        />
                    ))}
                </Box>
            </Box>

            {/* Optional */}
            <Box>
                <Typography variant="subtitle2" sx={{ mb: 1, color: theme.palette.text.secondary, fontWeight: 600 }}>
                    OPTIONAL
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                    {optional.map(dep => (
                        <DependencyRow
                            key={dep.id}
                            dep={dep}
                            installing={installing === dep.id}
                            onInstall={() => onInstall(dep.id)}
                        />
                    ))}
                </Box>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                <Button size="small" startIcon={<RefreshIcon />} onClick={onRefresh}>
                    Recheck All
                </Button>
            </Box>
        </Box>
    );
}

function DependencyRow({
    dep,
    installing,
    onInstall,
}: {
    dep: DependencyInfo;
    installing: boolean;
    onInstall: () => void;
}) {
    const theme = useTheme();
    const canInstall = dep.status === 'missing' || dep.status === 'outdated';
    const isCuda = dep.id === 'cuda';

    return (
        <Paper
            elevation={0}
            sx={{
                p: 1.5,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: 1,
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
            }}
        >
            <StatusIcon status={installing ? 'installing' : dep.status} />

            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {dep.name}
                    </Typography>
                    {dep.version && (
                        <Chip label={dep.version} size="small" sx={{ height: 18, fontSize: '0.65rem' }} />
                    )}
                    {dep.required && (
                        <Chip label="required" size="small" color="warning" variant="outlined" sx={{ height: 18, fontSize: '0.6rem' }} />
                    )}
                </Box>
                <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                    {dep.description}
                </Typography>
                {dep.error && (
                    <Typography variant="caption" sx={{ display: 'block', color: theme.palette.error.main, mt: 0.25 }}>
                        {dep.error}
                    </Typography>
                )}
                {dep.installedPath && dep.status === 'installed' && (
                    <Tooltip title={dep.installedPath}>
                        <Typography
                            variant="caption"
                            sx={{
                                display: 'block',
                                color: theme.palette.text.disabled,
                                fontSize: '0.6rem',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                                maxWidth: 300,
                            }}
                        >
                            {dep.installedPath}
                        </Typography>
                    </Tooltip>
                )}
            </Box>

            {canInstall && !isCuda && (
                <Button
                    size="small"
                    variant="contained"
                    startIcon={installing ? <CircularProgress size={14} color="inherit" /> : <DownloadIcon />}
                    onClick={onInstall}
                    disabled={installing}
                    sx={{ textTransform: 'none', fontSize: '0.75rem', whiteSpace: 'nowrap' }}
                >
                    {installing ? 'Installing...' : dep.status === 'outdated' ? 'Update' : 'Install'}
                </Button>
            )}
            {canInstall && isCuda && (
                <Tooltip title="CUDA must be installed manually from the NVIDIA website">
                    <Typography variant="caption" sx={{ color: theme.palette.text.disabled, fontStyle: 'italic' }}>
                        Manual install
                    </Typography>
                </Tooltip>
            )}
        </Paper>
    );
}

// ── Step 2: Ready ──

function ReadyStep({ scanResult }: { scanResult: SystemScanResult | null }) {
    const theme = useTheme();
    const tier = scanResult?.recommendation.tier ?? 'standard';
    const tierColor = TIER_COLORS[tier];

    return (
        <Box sx={{ textAlign: 'center', py: 4 }}>
            <CheckCircleIcon sx={{ fontSize: 64, color: '#4caf50', mb: 2 }} />
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
                You're all set!
            </Typography>
            <Typography sx={{ color: theme.palette.text.secondary, mb: 3, maxWidth: 400, mx: 'auto' }}>
                FreeMoCap is ready to go. You can always re-run this setup from the settings menu.
            </Typography>

            {scanResult && (
                <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1, flexWrap: 'wrap' }}>
                    <Chip
                        label={`${scanResult.recommendation.label} System`}
                        sx={{ borderColor: tierColor, color: tierColor, fontWeight: 600 }}
                        variant="outlined"
                    />
                    <Chip
                        label={`Up to ${scanResult.recommendation.maxCameras} cameras @ ${scanResult.recommendation.maxResolution}`}
                        variant="outlined"
                        size="small"
                    />
                </Box>
            )}
        </Box>
    );
}

// ── Main Wizard ──

interface SetupWizardProps {
    onComplete: () => void;
    /** When true, always shows the wizard regardless of persisted state */
    forceShow?: boolean;
}

export const SetupWizard: React.FC<SetupWizardProps> = ({ onComplete, forceShow = false }) => {
    const theme = useTheme();
    const { isElectron, api } = useElectronIPC();

    const [activeStep, setActiveStep] = useState(0);
    const [scanning, setScanning] = useState(false);
    const [scanResult, setScanResult] = useState<SystemScanResult | null>(null);
    const [dependencies, setDependencies] = useState<DependencyInfo[]>([]);
    const [installing, setInstalling] = useState<string | null>(null);

    // ── System scan ──

    const runScan = useCallback(async () => {
        if (!isElectron || !api) return;
        setScanning(true);
        try {
            const result = await api.system.scan.query();
            const typed = result as SystemScanResult;
            setScanResult(typed);
            // Persist scan result to ~/.freemocap/settings.json
            await api.settings.set.mutate({ key: SYSTEM_SCAN_KEY, value: typed });
        } catch (err) {
            console.error('System scan failed:', err);
        } finally {
            setScanning(false);
        }
    }, [isElectron, api]);

    // ── Dependency detection ──

    const detectDeps = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const result = await api.dependencies.detectAll.query();
            setDependencies(result as DependencyInfo[]);
        } catch (err) {
            console.error('Dependency detection failed:', err);
        }
    }, [isElectron, api]);

    // ── Install a dependency ──

    const installDep = useCallback(async (depId: string) => {
        if (!isElectron || !api) return;
        setInstalling(depId);
        try {
            const updated = await api.dependencies.install.mutate({ dependencyId: depId });
            setDependencies(prev =>
                prev.map(d => d.id === depId ? (updated as DependencyInfo) : d),
            );

            // After installing uv, re-detect python-env too (it depends on uv)
            if (depId === 'uv') {
                const envInfo = await api.dependencies.detect.query({ dependencyId: 'python-env' });
                setDependencies(prev =>
                    prev.map(d => d.id === 'python-env' ? (envInfo as DependencyInfo) : d),
                );
            }
        } catch (err) {
            console.error(`Failed to install ${depId}:`, err);
            setDependencies(prev =>
                prev.map(d =>
                    d.id === depId
                        ? { ...d, status: 'error' as DependencyStatus, error: err instanceof Error ? err.message : String(err) }
                        : d,
                ),
            );
        } finally {
            setInstalling(null);
        }
    }, [isElectron, api]);

    // ── Load persisted scan result on mount ──

    useEffect(() => {
        if (!isElectron || !api) return;
        api.settings.get.query({ key: SYSTEM_SCAN_KEY }).then(result => {
            if (result && typeof result === 'object' && 'cpu' in (result as object)) {
                setScanResult(result as SystemScanResult);
            }
        }).catch(() => { /* no persisted scan — will run fresh */ });
    }, [isElectron, api]);

    // ── Auto-run on step change ──

    useEffect(() => {
        if (activeStep === 0 && !scanResult && !scanning) {
            runScan();
        }
    }, [activeStep, scanResult, scanning, runScan]);

    useEffect(() => {
        if (activeStep === 1 && dependencies.length === 0) {
            detectDeps();
        }
    }, [activeStep, dependencies.length, detectDeps]);

    // ── Completion ──

    const handleFinish = useCallback(() => {
        if (isElectron && api) {
            api.settings.set.mutate({ key: SETUP_COMPLETE_KEY, value: true }).catch(err => {
                console.error('Failed to persist setup complete state:', err);
            });
        }
        onComplete();
    }, [onComplete, isElectron, api]);

    // ── Navigation ──

    const canProceed = (): boolean => {
        if (activeStep === 0) return scanResult !== null;
        if (activeStep === 1) return true; // Dependencies are not blocking
        return true;
    };

    // If not in Electron, show a simple non-Electron message
    if (!isElectron) {
        return (
            <Box sx={{ p: 4, textAlign: 'center' }}>
                <Typography variant="h6" sx={{ mb: 2 }}>Setup Wizard</Typography>
                <Typography sx={{ color: theme.palette.text.secondary, mb: 3 }}>
                    The setup wizard is only available in the desktop app.
                    Connect to a running FreeMoCap server to get started.
                </Typography>
                <Button variant="contained" onClick={onComplete}>Continue</Button>
            </Box>
        );
    }

    return (
        <Box
            sx={{
                width: '100%',
                maxWidth: 640,
                mx: 'auto',
                p: 3,
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
            }}
        >
            {/* Header */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <Typography variant="h6" sx={{ fontWeight: 700 }}>
                    FreeMoCap Setup
                </Typography>
                <Tooltip title="Skip setup">
                    <IconButton size="small" onClick={handleFinish}>
                        <CloseIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                </Tooltip>
            </Box>

            {/* Stepper */}
            <Stepper activeStep={activeStep} alternativeLabel sx={{ mb: 1 }}>
                {STEPS.map(label => (
                    <Step key={label}>
                        <StepLabel>{label}</StepLabel>
                    </Step>
                ))}
            </Stepper>

            {/* Step Content */}
            <Box sx={{ minHeight: 300 }}>
                {activeStep === 0 && (
                    <SystemScanStep
                        scanResult={scanResult}
                        scanning={scanning}
                        onRescan={runScan}
                    />
                )}
                {activeStep === 1 && (
                    <DependenciesStep
                        dependencies={dependencies}
                        installing={installing}
                        onInstall={installDep}
                        onRefresh={detectDeps}
                    />
                )}
                {activeStep === 2 && (
                    <ReadyStep scanResult={scanResult} />
                )}
            </Box>

            {/* Navigation Buttons */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                <Button
                    disabled={activeStep === 0}
                    onClick={() => setActiveStep(prev => prev - 1)}
                    startIcon={<ArrowBackIcon />}
                    sx={{ textTransform: 'none' }}
                >
                    Back
                </Button>

                {activeStep < STEPS.length - 1 ? (
                    <Button
                        variant="contained"
                        disabled={!canProceed()}
                        onClick={() => setActiveStep(prev => prev + 1)}
                        endIcon={<ArrowForwardIcon />}
                        sx={{ textTransform: 'none' }}
                    >
                        Next
                    </Button>
                ) : (
                    <Button
                        variant="contained"
                        color="success"
                        onClick={handleFinish}
                        sx={{ textTransform: 'none', fontWeight: 600 }}
                    >
                        Get Started
                    </Button>
                )}
            </Box>
        </Box>
    );
};

// ── Hook: should the wizard be shown? ──
// Reads from ~/.freemocap/settings.json via electron IPC.
// Returns { loading, required } — `required` is true until we've confirmed
// the file says setup is complete.

export function useSetupWizardRequired(): { loading: boolean; required: boolean } {
    const { isElectron, api } = useElectronIPC();
    const [loading, setLoading] = useState(true);
    const [required, setRequired] = useState(true);

    useEffect(() => {
        if (!isElectron || !api) {
            // Not in Electron — never show the wizard
            setRequired(false);
            setLoading(false);
            return;
        }

        api.settings.get.query({ key: SETUP_COMPLETE_KEY })
            .then(value => {
                setRequired(value !== true);
            })
            .catch(() => {
                // Settings file doesn't exist yet — setup is required
                setRequired(true);
            })
            .finally(() => {
                setLoading(false);
            });
    }, [isElectron, api]);

    return { loading, required };
}
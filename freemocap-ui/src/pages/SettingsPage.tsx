import React, { useState, useCallback, useEffect } from 'react';
import {
    Box,
    Typography,
    Switch,
    FormControlLabel,
    TextField,
    Slider,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Paper,
    List,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    Divider,
    Chip,
    Button,
    CircularProgress,
    Alert,
    Tooltip,
    LinearProgress,
    IconButton,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import PaletteIcon from '@mui/icons-material/Palette';
import DnsIcon from '@mui/icons-material/Dns';
import FiberManualRecordIcon from '@mui/icons-material/FiberManualRecord';
import SquareFootIcon from '@mui/icons-material/SquareFoot';
import DirectionsRunIcon from '@mui/icons-material/DirectionsRun';
import CastConnectedIcon from '@mui/icons-material/CastConnected';
import ComputerIcon from '@mui/icons-material/Computer';
import MemoryIcon from '@mui/icons-material/Memory';
import SpeedIcon from '@mui/icons-material/Speed';
import StorageIcon from '@mui/icons-material/Storage';
import VideocamIcon from '@mui/icons-material/Videocam';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import DownloadIcon from '@mui/icons-material/Download';
import RefreshIcon from '@mui/icons-material/Refresh';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import CodeIcon from '@mui/icons-material/Code';
import { useNavigate } from 'react-router-dom';
import {
    useAppDispatch,
    useAppSelector,
    themeModeSet,
    themeModeToggled,
    recordingDirectoryChanged,
    useDelayStartToggled,
    delaySecondsChanged,
    useTimestampToggled,
    useIncrementToggled,
    baseNameChanged,
    recordingTagChanged,
    createSubfolderToggled,
    customSubfolderNameChanged,
    selectServerSettings,
} from '@/store';
import { ThemeMode } from '@/store/slices/theme/theme-types';
import { useCalibration } from '@/hooks/useCalibration';
import { useMocap } from '@/hooks/useMocap';
import { useServer } from '@/hooks/useServer';
import { useElectronIPC } from '@/services';
import {
    MediapipeModelComplexity,
    MEDIAPIPE_REALTIME_PRESET,
    MEDIAPIPE_POSTHOC_PRESET,
    DEFAULT_REALTIME_FILTER_CONFIG,
} from '@/store/slices/mocap';
import { SettingsEditor } from '@/components/settings-editor/SettingsEditor';

// ── Section IDs ──

type SectionId =
    | 'appearance'
    | 'connection'
    | 'recording'
    | 'calibration'
    | 'mocap'
    | 'vmc'
    | 'system'
    | 'editor';

interface SectionDef {
    id: SectionId;
    label: string;
    icon: React.ReactNode;
}

const SECTIONS: SectionDef[] = [
    { id: 'appearance', label: 'Appearance', icon: <PaletteIcon /> },
    { id: 'connection', label: 'Server Connection', icon: <DnsIcon /> },
    { id: 'recording', label: 'Recording', icon: <FiberManualRecordIcon /> },
    { id: 'calibration', label: 'Calibration', icon: <SquareFootIcon /> },
    { id: 'mocap', label: 'Motion Capture', icon: <DirectionsRunIcon /> },
    { id: 'vmc', label: 'VMC Output', icon: <CastConnectedIcon /> },
    { id: 'system', label: 'System Info', icon: <ComputerIcon /> },
    { id: 'editor', label: 'Raw Editor', icon: <CodeIcon /> },
];

// ── Setup wizard types (mirrors electron-side types) ──

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

const SYSTEM_SCAN_KEY = 'lastSystemScan';

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

// ── Shared layout components ──

function SectionHeader({ title, description }: { title: string; description?: string }) {
    const theme = useTheme();
    return (
        <Box sx={{ mb: 3 }}>
            <Typography variant="h5" sx={{ fontWeight: 700, mb: 0.5 }}>
                {title}
            </Typography>
            {description && (
                <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                    {description}
                </Typography>
            )}
        </Box>
    );
}

function SettingRow({ label, description, children }: { label: string; description?: string; children: React.ReactNode }) {
    const theme = useTheme();
    return (
        <Box
            sx={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                py: 1.5,
                gap: 3,
            }}
        >
            <Box sx={{ flex: 1, minWidth: 0 }}>
                <Typography variant="body1" sx={{ fontWeight: 500 }}>
                    {label}
                </Typography>
                {description && (
                    <Typography variant="body2" sx={{ color: theme.palette.text.secondary, mt: 0.25 }}>
                        {description}
                    </Typography>
                )}
            </Box>
            <Box sx={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
                {children}
            </Box>
        </Box>
    );
}

function SettingGroup({ title, children }: { title: string; children: React.ReactNode }) {
    const theme = useTheme();
    return (
        <Paper
            elevation={0}
            sx={{
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: 2,
                p: 2.5,
                mb: 2,
            }}
        >
            <Typography
                variant="overline"
                sx={{
                    fontWeight: 700,
                    color: theme.palette.text.secondary,
                    letterSpacing: 1.2,
                    mb: 1,
                    display: 'block',
                }}
            >
                {title}
            </Typography>
            <Divider sx={{ mb: 1 }} />
            {children}
        </Paper>
    );
}

// ── Section: Appearance ──

function AppearanceSection() {
    const dispatch = useAppDispatch();
    const themeMode = useAppSelector(state => state.theme.mode);

    return (
        <>
            <SectionHeader
                title="Appearance"
                description="Customize how FreeMoCap looks."
            />
            <SettingGroup title="Theme">
                <SettingRow
                    label="Dark Mode"
                    description="Toggle between light and dark color schemes."
                >
                    <Switch
                        checked={themeMode === 'dark'}
                        onChange={() => dispatch(themeModeToggled())}
                    />
                </SettingRow>
                <SettingRow
                    label="Color Scheme"
                    description="Choose your preferred theme."
                >
                    <FormControl size="small" sx={{ minWidth: 140 }}>
                        <Select
                            value={themeMode}
                            onChange={(e) => dispatch(themeModeSet(e.target.value as ThemeMode))}
                        >
                            <MenuItem value="dark">Dark</MenuItem>
                            <MenuItem value="light">Light</MenuItem>
                        </Select>
                    </FormControl>
                </SettingRow>
            </SettingGroup>
        </>
    );
}

// ── Section: Server Connection ──

function ConnectionSection() {
    const { isConnected, connectionState, connect, disconnect } = useServer();
    const theme = useTheme();

    return (
        <>
            <SectionHeader
                title="Server Connection"
                description="Connection to the FreeMoCap backend server."
            />
            <SettingGroup title="Status">
                <SettingRow
                    label="Connection Status"
                    description={`Current state: ${connectionState}`}
                >
                    <Chip
                        label={isConnected ? 'Connected' : 'Disconnected'}
                        color={isConnected ? 'success' : 'error'}
                        size="small"
                        variant="outlined"
                    />
                </SettingRow>
                <SettingRow
                    label="Server Address"
                    description="Backend server URL (configured at build time)."
                >
                    <Typography variant="body2" sx={{ fontFamily: 'monospace', color: theme.palette.text.secondary }}>
                        localhost:53117
                    </Typography>
                </SettingRow>
                <SettingRow label="Actions">
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Button
                            size="small"
                            variant="outlined"
                            onClick={connect}
                            disabled={isConnected}
                        >
                            Connect
                        </Button>
                        <Button
                            size="small"
                            variant="outlined"
                            color="error"
                            onClick={disconnect}
                            disabled={!isConnected}
                        >
                            Disconnect
                        </Button>
                    </Box>
                </SettingRow>
            </SettingGroup>
        </>
    );
}

// ── Section: Recording ──

function RecordingSection() {
    const dispatch = useAppDispatch();
    const recording = useAppSelector(state => state.recording);
    const { isElectron, api } = useElectronIPC();

    const handleBrowseDirectory = useCallback(async () => {
        if (!isElectron || !api) return;
        const result = await api.fileSystem.selectDirectory.query();
        if (result) {
            dispatch(recordingDirectoryChanged(result as string));
        }
    }, [dispatch, isElectron, api]);

    return (
        <>
            <SectionHeader
                title="Recording"
                description="Configure how recordings are saved and named."
            />
            <SettingGroup title="Storage">
                <SettingRow
                    label="Recording Directory"
                    description="Base folder for saving recordings."
                >
                    <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                        <TextField
                            size="small"
                            value={recording.recordingDirectory}
                            onChange={(e) => dispatch(recordingDirectoryChanged(e.target.value))}
                            sx={{ minWidth: 260 }}
                            inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
                        />
                        {isElectron && (
                            <Button size="small" variant="outlined" onClick={handleBrowseDirectory}>
                                Browse
                            </Button>
                        )}
                    </Box>
                </SettingRow>
                <SettingRow
                    label="Create Subfolder"
                    description="Put each recording session in its own subfolder."
                >
                    <Switch
                        checked={recording.config.createSubfolder}
                        onChange={(_, v) => dispatch(createSubfolderToggled(v))}
                    />
                </SettingRow>
                {recording.config.createSubfolder && (
                    <SettingRow
                        label="Custom Subfolder Name"
                        description="Leave blank for auto-generated timestamp name."
                    >
                        <TextField
                            size="small"
                            value={recording.config.customSubfolderName}
                            onChange={(e) => dispatch(customSubfolderNameChanged(e.target.value))}
                            placeholder="(auto)"
                            sx={{ minWidth: 200 }}
                        />
                    </SettingRow>
                )}
            </SettingGroup>

            <SettingGroup title="Naming">
                <SettingRow
                    label="Use Timestamp"
                    description="Include timestamp in recording name."
                >
                    <Switch
                        checked={recording.config.useTimestamp}
                        onChange={(_, v) => dispatch(useTimestampToggled(v))}
                    />
                </SettingRow>
                <SettingRow
                    label="Use Increment"
                    description="Append an auto-incrementing number."
                >
                    <Switch
                        checked={recording.config.useIncrement}
                        onChange={(_, v) => dispatch(useIncrementToggled(v))}
                    />
                </SettingRow>
                {!recording.config.useTimestamp && (
                    <SettingRow
                        label="Base Name"
                        description="Base name for recordings when not using timestamp."
                    >
                        <TextField
                            size="small"
                            value={recording.config.baseName}
                            onChange={(e) => dispatch(baseNameChanged(e.target.value))}
                            sx={{ minWidth: 200 }}
                        />
                    </SettingRow>
                )}
                <SettingRow
                    label="Recording Tag"
                    description="Optional tag appended to the recording name."
                >
                    <TextField
                        size="small"
                        value={recording.config.recordingTag}
                        onChange={(e) => dispatch(recordingTagChanged(e.target.value))}
                        placeholder="(none)"
                        sx={{ minWidth: 200 }}
                    />
                </SettingRow>
            </SettingGroup>

            <SettingGroup title="Delay Start">
                <SettingRow
                    label="Delay Before Recording"
                    description="Add a countdown before recording starts."
                >
                    <Switch
                        checked={recording.config.useDelayStart}
                        onChange={(_, v) => dispatch(useDelayStartToggled(v))}
                    />
                </SettingRow>
                {recording.config.useDelayStart && (
                    <SettingRow
                        label="Delay Duration"
                        description="Seconds to wait before recording begins."
                    >
                        <TextField
                            size="small"
                            type="number"
                            value={recording.config.delaySeconds}
                            onChange={(e) => dispatch(delaySecondsChanged(Number(e.target.value)))}
                            inputProps={{ min: 1, max: 30 }}
                            sx={{ width: 100 }}
                        />
                    </SettingRow>
                )}
            </SettingGroup>

            <SettingGroup title="Preview">
                <Box sx={{ fontFamily: 'monospace', fontSize: 13, opacity: 0.7, p: 1 }}>
                    <Typography variant="caption" sx={{ display: 'block' }}>
                        Recording name: <strong>{recording.computed.recordingName || '(empty)'}</strong>
                    </Typography>
                    <Typography variant="caption" sx={{ display: 'block' }}>
                        Full path: <strong>{recording.computed.fullRecordingPath}</strong>
                    </Typography>
                </Box>
            </SettingGroup>
        </>
    );
}

// ── Section: Calibration ──

function CalibrationSection() {
    const { config, updateCalibrationConfig, isLoading } = useCalibration();

    return (
        <>
            <SectionHeader
                title="Calibration"
                description="Camera calibration settings for multi-camera setups."
            />
            <SettingGroup title="ChArUco Board">
                <SettingRow
                    label="X Squares"
                    description="Number of squares along the X axis."
                >
                    <TextField
                        size="small"
                        type="number"
                        value={config.charucoBoardXSquares}
                        onChange={(e) => updateCalibrationConfig({ charucoBoardXSquares: Number(e.target.value) })}
                        inputProps={{ min: 2, max: 20 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
                <SettingRow
                    label="Y Squares"
                    description="Number of squares along the Y axis."
                >
                    <TextField
                        size="small"
                        type="number"
                        value={config.charucoBoardYSquares}
                        onChange={(e) => updateCalibrationConfig({ charucoBoardYSquares: Number(e.target.value) })}
                        inputProps={{ min: 2, max: 20 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
                <SettingRow
                    label="Square Length (mm)"
                    description="Physical size of each square on the board."
                >
                    <TextField
                        size="small"
                        type="number"
                        value={config.charucoSquareLength}
                        onChange={(e) => updateCalibrationConfig({ charucoSquareLength: Number(e.target.value) })}
                        inputProps={{ min: 1, step: 0.5 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
            </SettingGroup>

            <SettingGroup title="Solver">
                <SettingRow
                    label="Solver Method"
                    description="Algorithm used to solve camera calibration."
                >
                    <FormControl size="small" sx={{ minWidth: 140 }}>
                        <Select
                            value={config.solverMethod}
                            onChange={(e) => updateCalibrationConfig({ solverMethod: e.target.value as 'anipose' | 'pyceres' })}
                            disabled={isLoading}
                        >
                            <MenuItem value="anipose">Anipose</MenuItem>
                            <MenuItem value="pyceres">PyCeres</MenuItem>
                        </Select>
                    </FormControl>
                </SettingRow>
                <SettingRow
                    label="Use Ground Plane"
                    description="Apply ground plane constraint to calibration."
                >
                    <Switch
                        checked={config.useGroundplane}
                        onChange={(_, v) => updateCalibrationConfig({ useGroundplane: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
            </SettingGroup>

            <SettingGroup title="Recording">
                <SettingRow
                    label="Live Track ChArUco"
                    description="Show ChArUco detection overlay while recording."
                >
                    <Switch
                        checked={config.liveTrackCharuco}
                        onChange={(_, v) => updateCalibrationConfig({ liveTrackCharuco: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
                <SettingRow
                    label="Min Shared Views Per Camera"
                    description="Minimum board observations shared between camera pairs."
                >
                    <TextField
                        size="small"
                        type="number"
                        value={config.minSharedViewsPerCamera}
                        onChange={(e) => updateCalibrationConfig({ minSharedViewsPerCamera: Number(e.target.value) })}
                        inputProps={{ min: 1, max: 200 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
                <SettingRow
                    label="Auto-Stop on Min View Count"
                    description="Automatically stop recording when minimum views are reached."
                >
                    <Switch
                        checked={config.autoStopOnMinViewCount}
                        onChange={(_, v) => updateCalibrationConfig({ autoStopOnMinViewCount: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
            </SettingGroup>
        </>
    );
}

// ── Section: Motion Capture ──

const MODEL_COMPLEXITY_LABELS: Record<MediapipeModelComplexity, string> = {
    0: 'Lite (fastest)',
    1: 'Full (balanced)',
    2: 'Heavy (most accurate)',
};

function MocapSection() {
    const {
        detectorConfig,
        skeletonFilterConfig,
        updateDetectorConfig,
        replaceDetectorConfig,
        updateSkeletonFilterConfig,
        replaceSkeletonFilterConfig,
        isLoading,
    } = useMocap();

    const detectPreset = useCallback(() => {
        if (
            detectorConfig.model_complexity === 0 &&
            !detectorConfig.enable_segmentation &&
            !detectorConfig.smooth_segmentation
        ) return 'realtime';
        if (
            detectorConfig.model_complexity === 2 &&
            detectorConfig.enable_segmentation &&
            detectorConfig.smooth_segmentation
        ) return 'posthoc';
        return 'custom';
    }, [detectorConfig]);

    const currentPreset = detectPreset();

    return (
        <>
            <SectionHeader
                title="Motion Capture"
                description="MediaPipe detector and skeleton filter configuration."
            />

            {/* Detector */}
            <SettingGroup title="MediaPipe Detector">
                <SettingRow
                    label="Preset"
                    description="Quick-select a tuned detector configuration."
                >
                    <Box sx={{ display: 'flex', gap: 1 }}>
                        <Chip
                            label="Realtime"
                            size="small"
                            variant={currentPreset === 'realtime' ? 'filled' : 'outlined'}
                            color={currentPreset === 'realtime' ? 'primary' : 'default'}
                            onClick={() => replaceDetectorConfig({ ...MEDIAPIPE_REALTIME_PRESET })}
                            disabled={isLoading}
                            sx={{ cursor: 'pointer' }}
                        />
                        <Chip
                            label="Posthoc"
                            size="small"
                            variant={currentPreset === 'posthoc' ? 'filled' : 'outlined'}
                            color={currentPreset === 'posthoc' ? 'primary' : 'default'}
                            onClick={() => replaceDetectorConfig({ ...MEDIAPIPE_POSTHOC_PRESET })}
                            disabled={isLoading}
                            sx={{ cursor: 'pointer' }}
                        />
                        {currentPreset === 'custom' && (
                            <Chip label="Custom" size="small" variant="outlined" color="warning" />
                        )}
                    </Box>
                </SettingRow>
                <SettingRow
                    label="Model Complexity"
                    description="Controls accuracy vs. speed tradeoff."
                >
                    <FormControl size="small" sx={{ minWidth: 180 }}>
                        <Select
                            value={detectorConfig.model_complexity}
                            onChange={(e) => updateDetectorConfig({ model_complexity: e.target.value as MediapipeModelComplexity })}
                            disabled={isLoading}
                        >
                            <MenuItem value={0}>{MODEL_COMPLEXITY_LABELS[0]}</MenuItem>
                            <MenuItem value={1}>{MODEL_COMPLEXITY_LABELS[1]}</MenuItem>
                            <MenuItem value={2}>{MODEL_COMPLEXITY_LABELS[2]}</MenuItem>
                        </Select>
                    </FormControl>
                </SettingRow>
                <SettingRow
                    label={`Min Detection Confidence: ${detectorConfig.min_detection_confidence.toFixed(2)}`}
                    description="Minimum score for initial pose detection."
                >
                    <Slider
                        value={detectorConfig.min_detection_confidence}
                        onChange={(_, v) => updateDetectorConfig({ min_detection_confidence: v as number })}
                        min={0} max={1} step={0.05} size="small"
                        disabled={isLoading}
                        sx={{ width: 180 }}
                    />
                </SettingRow>
                <SettingRow
                    label={`Min Tracking Confidence: ${detectorConfig.min_tracking_confidence.toFixed(2)}`}
                    description="Minimum score for frame-to-frame tracking."
                >
                    <Slider
                        value={detectorConfig.min_tracking_confidence}
                        onChange={(_, v) => updateDetectorConfig({ min_tracking_confidence: v as number })}
                        min={0} max={1} step={0.05} size="small"
                        disabled={isLoading}
                        sx={{ width: 180 }}
                    />
                </SettingRow>
                <SettingRow label="Smooth Landmarks">
                    <Switch
                        size="small"
                        checked={detectorConfig.smooth_landmarks}
                        onChange={(_, v) => updateDetectorConfig({ smooth_landmarks: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
                <SettingRow label="Enable Segmentation">
                    <Switch
                        size="small"
                        checked={detectorConfig.enable_segmentation}
                        onChange={(_, v) => updateDetectorConfig({ enable_segmentation: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
                <SettingRow label="Smooth Segmentation">
                    <Switch
                        size="small"
                        checked={detectorConfig.smooth_segmentation}
                        onChange={(_, v) => updateDetectorConfig({ smooth_segmentation: v })}
                        disabled={isLoading || !detectorConfig.enable_segmentation}
                    />
                </SettingRow>
                <SettingRow label="Refine Face Landmarks">
                    <Switch
                        size="small"
                        checked={detectorConfig.refine_face_landmarks}
                        onChange={(_, v) => updateDetectorConfig({ refine_face_landmarks: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
                <SettingRow label="Static Image Mode">
                    <Switch
                        size="small"
                        checked={detectorConfig.static_image_mode}
                        onChange={(_, v) => updateDetectorConfig({ static_image_mode: v })}
                        disabled={isLoading}
                    />
                </SettingRow>
            </SettingGroup>

            {/* Skeleton Filter */}
            <SettingGroup title="Skeleton Filter">
                <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1 }}>
                    <Button
                        size="small"
                        variant="text"
                        onClick={() => replaceSkeletonFilterConfig({ ...DEFAULT_REALTIME_FILTER_CONFIG })}
                        disabled={isLoading}
                    >
                        Reset Defaults
                    </Button>
                </Box>

                <SettingRow
                    label="Height (meters)"
                    description="Subject height for bone length estimation."
                >
                    <TextField
                        size="small"
                        type="number"
                        value={skeletonFilterConfig.height_meters}
                        onChange={(e) => updateSkeletonFilterConfig({ height_meters: Number(e.target.value) })}
                        inputProps={{ min: 0.5, max: 2.5, step: 0.01 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>

                <Typography variant="caption" sx={{ display: 'block', mt: 1, mb: 0.5, fontWeight: 600, opacity: 0.6 }}>
                    ONE EURO FILTER
                </Typography>
                <SettingRow label={`Min Cutoff: ${skeletonFilterConfig.min_cutoff.toFixed(2)}`}>
                    <Slider
                        value={skeletonFilterConfig.min_cutoff}
                        onChange={(_, v) => updateSkeletonFilterConfig({ min_cutoff: v as number })}
                        min={0.01} max={10} step={0.01} size="small"
                        disabled={isLoading} sx={{ width: 180 }}
                    />
                </SettingRow>
                <SettingRow label={`Beta: ${skeletonFilterConfig.beta.toFixed(3)}`}>
                    <Slider
                        value={skeletonFilterConfig.beta}
                        onChange={(_, v) => updateSkeletonFilterConfig({ beta: v as number })}
                        min={0} max={1} step={0.001} size="small"
                        disabled={isLoading} sx={{ width: 180 }}
                    />
                </SettingRow>
                <SettingRow label={`D Cutoff: ${skeletonFilterConfig.d_cutoff.toFixed(2)}`}>
                    <Slider
                        value={skeletonFilterConfig.d_cutoff}
                        onChange={(_, v) => updateSkeletonFilterConfig({ d_cutoff: v as number })}
                        min={0.01} max={10} step={0.01} size="small"
                        disabled={isLoading} sx={{ width: 180 }}
                    />
                </SettingRow>

                <Typography variant="caption" sx={{ display: 'block', mt: 1, mb: 0.5, fontWeight: 600, opacity: 0.6 }}>
                    FABRIK IK
                </Typography>
                <SettingRow label={`Tolerance: ${skeletonFilterConfig.fabrik_tolerance.toFixed(4)}`}>
                    <Slider
                        value={skeletonFilterConfig.fabrik_tolerance}
                        onChange={(_, v) => updateSkeletonFilterConfig({ fabrik_tolerance: v as number })}
                        min={0.0001} max={0.1} step={0.0001} size="small"
                        disabled={isLoading} sx={{ width: 180 }}
                    />
                </SettingRow>
                <SettingRow label="Max Iterations">
                    <TextField
                        size="small"
                        type="number"
                        value={skeletonFilterConfig.fabrik_max_iterations}
                        onChange={(e) => updateSkeletonFilterConfig({ fabrik_max_iterations: Number(e.target.value) })}
                        inputProps={{ min: 1, max: 100 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>

                <Typography variant="caption" sx={{ display: 'block', mt: 1, mb: 0.5, fontWeight: 600, opacity: 0.6 }}>
                    POINT GATING
                </Typography>
                <SettingRow label="Max Reprojection Error (px)">
                    <TextField
                        size="small"
                        type="number"
                        value={skeletonFilterConfig.max_reprojection_error_px}
                        onChange={(e) => updateSkeletonFilterConfig({ max_reprojection_error_px: Number(e.target.value) })}
                        inputProps={{ min: 0, step: 1 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
                <SettingRow label="Max Velocity (m/s)">
                    <TextField
                        size="small"
                        type="number"
                        value={skeletonFilterConfig.max_velocity_m_per_s}
                        onChange={(e) => updateSkeletonFilterConfig({ max_velocity_m_per_s: Number(e.target.value) })}
                        inputProps={{ min: 0, step: 0.5 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
                <SettingRow label="Max Rejected Streak">
                    <TextField
                        size="small"
                        type="number"
                        value={skeletonFilterConfig.max_rejected_streak}
                        onChange={(e) => updateSkeletonFilterConfig({ max_rejected_streak: Number(e.target.value) })}
                        inputProps={{ min: 0 }}
                        disabled={isLoading}
                        sx={{ width: 100 }}
                    />
                </SettingRow>
            </SettingGroup>
        </>
    );
}

// ── Section: VMC Output ──

function VMCSection() {
    const { send, isConnected } = useServer();
    const settings = useAppSelector(selectServerSettings);

    const vmcEnabled = settings?.vmc?.enabled ?? false;
    const vmcHost = settings?.vmc?.host ?? '127.0.0.1';
    const vmcPort = settings?.vmc?.port ?? 39539;

    const patchVMC = useCallback(
        (patch: Record<string, unknown>) => {
            send({ message_type: 'settings/patch', patch: { vmc: patch } });
        },
        [send],
    );

    return (
        <>
            <SectionHeader
                title="VMC Output"
                description="Virtual Motion Capture protocol streaming settings."
            />
            <SettingGroup title="VMC Streaming">
                <SettingRow
                    label="Enable VMC Output"
                    description="Stream skeleton data via VMC protocol over UDP."
                >
                    <Switch
                        checked={vmcEnabled}
                        onChange={() => patchVMC({ enabled: !vmcEnabled })}
                        disabled={!isConnected}
                    />
                </SettingRow>
                <SettingRow
                    label="Host"
                    description="Target IP address for VMC packets."
                >
                    <TextField
                        size="small"
                        value={vmcHost}
                        onChange={(e) => {
                            const val = e.target.value.trim();
                            if (val.length > 0) patchVMC({ host: val });
                        }}
                        disabled={!isConnected || !vmcEnabled}
                        sx={{ width: 160 }}
                        inputProps={{ style: { fontFamily: 'monospace', fontSize: 13 } }}
                    />
                </SettingRow>
                <SettingRow
                    label="Port"
                    description="UDP port for VMC packets (default 39539)."
                >
                    <TextField
                        size="small"
                        type="number"
                        value={vmcPort}
                        onChange={(e) => {
                            const val = parseInt(e.target.value, 10);
                            if (!isNaN(val) && val > 0 && val <= 65535) patchVMC({ port: val });
                        }}
                        disabled={!isConnected || !vmcEnabled}
                        inputProps={{ min: 1, max: 65535 }}
                        sx={{ width: 120 }}
                    />
                </SettingRow>
                {!isConnected && (
                    <Alert severity="info" sx={{ mt: 1 }}>
                        Connect to the backend server to configure VMC settings.
                    </Alert>
                )}
            </SettingGroup>
        </>
    );
}

// ── Section: System Info ──

function DependencyStatusIcon({ status }: { status: DependencyStatus }) {
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

function SystemSection() {
    const theme = useTheme();
    const { isElectron, api } = useElectronIPC();

    const [scanning, setScanning] = useState(false);
    const [scanResult, setScanResult] = useState<SystemScanResult | null>(null);
    const [dependencies, setDependencies] = useState<DependencyInfo[]>([]);
    const [installing, setInstalling] = useState<string | null>(null);

    const runScan = useCallback(async () => {
        if (!isElectron || !api) return;
        setScanning(true);
        try {
            const result = await api.system.scan.query();
            const typed = result as SystemScanResult;
            setScanResult(typed);
            await api.settings.set.mutate({ key: SYSTEM_SCAN_KEY, value: typed });
        } catch (err) {
            console.error('System scan failed:', err);
        } finally {
            setScanning(false);
        }
    }, [isElectron, api]);

    const detectDeps = useCallback(async () => {
        if (!isElectron || !api) return;
        try {
            const result = await api.dependencies.detectAll.query();
            setDependencies(result as DependencyInfo[]);
        } catch (err) {
            console.error('Dependency detection failed:', err);
        }
    }, [isElectron, api]);

    const installDep = useCallback(async (depId: string) => {
        if (!isElectron || !api) return;
        setInstalling(depId);
        try {
            const updated = await api.dependencies.install.mutate({ dependencyId: depId });
            setDependencies(prev =>
                prev.map(d => d.id === depId ? (updated as DependencyInfo) : d),
            );
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

    // Load persisted scan on mount
    useEffect(() => {
        if (!isElectron || !api) return;
        api.settings.get.query({ key: SYSTEM_SCAN_KEY }).then(result => {
            if (result && typeof result === 'object' && 'cpu' in (result as object)) {
                setScanResult(result as SystemScanResult);
            }
        }).catch(() => { /* no persisted scan */ });
    }, [isElectron, api]);

    if (!isElectron) {
        return (
            <>
                <SectionHeader
                    title="System Info"
                    description="System scanning is only available in the desktop app."
                />
                <Alert severity="info">
                    Connect to a running FreeMoCap server via the desktop app to view system information and manage dependencies.
                </Alert>
            </>
        );
    }

    const rec = scanResult?.recommendation;
    const tierColor = rec ? TIER_COLORS[rec.tier] : undefined;

    return (
        <>
            <SectionHeader
                title="System Info"
                description="Hardware information, performance tier, and dependency status."
            />

            {/* Performance Tier */}
            <SettingGroup title="Performance Tier">
                {scanning ? (
                    <Box sx={{ textAlign: 'center', py: 4 }}>
                        <CircularProgress size={40} />
                        <Typography sx={{ mt: 1.5, color: theme.palette.text.secondary }}>
                            Scanning your system...
                        </Typography>
                    </Box>
                ) : scanResult && rec ? (
                    <>
                        <Paper
                            elevation={0}
                            sx={{
                                p: 2, mb: 2,
                                border: `2px solid ${tierColor}`,
                                borderRadius: 2,
                                background: `${tierColor}11`,
                                textAlign: 'center',
                            }}
                        >
                            <Typography variant="h5" sx={{ fontWeight: 700, color: tierColor }}>
                                {TIER_EMOJIS[rec.tier]} {rec.label} System
                            </Typography>
                            <Typography variant="body2" sx={{ mt: 0.5, color: theme.palette.text.secondary }}>
                                {rec.description}
                            </Typography>
                            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1.5, mt: 1.5, flexWrap: 'wrap' }}>
                                <Chip
                                    icon={<VideocamIcon />}
                                    label={`Up to ${rec.maxCameras} cameras`}
                                    size="small"
                                    sx={{ borderColor: tierColor, color: tierColor }}
                                    variant="outlined"
                                />
                                <Chip
                                    label={`${rec.maxResolution} max`}
                                    size="small"
                                    sx={{ borderColor: tierColor, color: tierColor }}
                                    variant="outlined"
                                />
                                {rec.realtimeTracking && (
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

                        {/* Hardware grid */}
                        <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 1.5, mb: 2 }}>
                            <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                    <MemoryIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                                    <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>CPU</Typography>
                                </Box>
                                <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>
                                    {scanResult.cpu.model}
                                </Typography>
                                <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                    {scanResult.cpu.threads} threads · {scanResult.cpu.cores} cores · {scanResult.cpu.speedMhz} MHz
                                </Typography>
                            </Paper>

                            <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                    <ComputerIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                                    <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>MEMORY</Typography>
                                </Box>
                                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                    {scanResult.ram.totalGb} GB total
                                </Typography>
                                <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                    {scanResult.ram.availableGb} GB available
                                </Typography>
                            </Paper>

                            <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                    <SpeedIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                                    <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>GPU</Typography>
                                </Box>
                                {scanResult.gpus.length > 0 ? scanResult.gpus.map((gpu, i) => (
                                    <Box key={i}>
                                        <Typography variant="body2" sx={{ fontWeight: 500, fontSize: '0.8rem' }}>
                                            {gpu.name}
                                        </Typography>
                                        <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                            {gpu.vramMb ? `${Math.round(gpu.vramMb / 1024)} GB VRAM` : 'VRAM unknown'}
                                            {gpu.cudaAvailable ? ` · CUDA ${gpu.cudaVersion || '✓'}` : ''}
                                        </Typography>
                                    </Box>
                                )) : (
                                    <Typography variant="body2" sx={{ color: theme.palette.text.disabled }}>
                                        No dedicated GPU detected
                                    </Typography>
                                )}
                            </Paper>

                            <Paper elevation={0} sx={{ p: 1.5, border: `1px solid ${theme.palette.divider}`, borderRadius: 1 }}>
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                                    <StorageIcon sx={{ fontSize: 18, color: theme.palette.text.secondary }} />
                                    <Typography variant="caption" sx={{ fontWeight: 600, color: theme.palette.text.secondary }}>DISK</Typography>
                                </Box>
                                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                                    {scanResult.disk.freeGb} GB free
                                </Typography>
                                <Typography variant="caption" sx={{ color: theme.palette.text.secondary }}>
                                    of {scanResult.disk.totalGb} GB total
                                </Typography>
                                {scanResult.disk.freeGb > 0 && scanResult.disk.freeGb < 20 && (
                                    <LinearProgress
                                        variant="determinate"
                                        value={((scanResult.disk.totalGb - scanResult.disk.freeGb) / scanResult.disk.totalGb) * 100}
                                        color="warning"
                                        sx={{ mt: 0.5, height: 4, borderRadius: 1 }}
                                    />
                                )}
                            </Paper>
                        </Box>

                        {rec.warnings.length > 0 && (
                            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5, mb: 2 }}>
                                {rec.warnings.map((w, i) => (
                                    <Alert key={i} severity="warning" sx={{ py: 0, fontSize: '0.75rem' }}>
                                        {w}
                                    </Alert>
                                ))}
                            </Box>
                        )}
                    </>
                ) : (
                    <Box sx={{ textAlign: 'center', py: 3 }}>
                        <Typography sx={{ color: theme.palette.text.secondary, mb: 1 }}>
                            No system scan data available.
                        </Typography>
                    </Box>
                )}

                <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <Button
                        size="small"
                        startIcon={scanning ? <CircularProgress size={14} /> : <RefreshIcon />}
                        onClick={runScan}
                        disabled={scanning}
                    >
                        {scanResult ? 'Rescan' : 'Scan System'}
                    </Button>
                </Box>
            </SettingGroup>

            {/* Dependencies */}
            <SettingGroup title="Dependencies">
                {dependencies.length === 0 ? (
                    <Box sx={{ textAlign: 'center', py: 3 }}>
                        <Typography sx={{ color: theme.palette.text.secondary, mb: 1 }}>
                            No dependency data loaded.
                        </Typography>
                        <Button size="small" startIcon={<RefreshIcon />} onClick={detectDeps}>
                            Check Dependencies
                        </Button>
                    </Box>
                ) : (
                    <>
                        {dependencies.filter(d => d.required).length > 0 && (
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="caption" sx={{ fontWeight: 700, color: theme.palette.text.secondary, mb: 0.5, display: 'block' }}>
                                    REQUIRED
                                </Typography>
                                {dependencies.filter(d => d.required).map(dep => (
                                    <DependencyRow
                                        key={dep.id}
                                        dep={dep}
                                        isInstalling={installing === dep.id}
                                        onInstall={() => installDep(dep.id)}
                                    />
                                ))}
                            </Box>
                        )}
                        {dependencies.filter(d => !d.required).length > 0 && (
                            <Box>
                                <Typography variant="caption" sx={{ fontWeight: 700, color: theme.palette.text.secondary, mb: 0.5, display: 'block' }}>
                                    OPTIONAL
                                </Typography>
                                {dependencies.filter(d => !d.required).map(dep => (
                                    <DependencyRow
                                        key={dep.id}
                                        dep={dep}
                                        isInstalling={installing === dep.id}
                                        onInstall={() => installDep(dep.id)}
                                    />
                                ))}
                            </Box>
                        )}
                        <Box sx={{ display: 'flex', justifyContent: 'flex-end', mt: 1 }}>
                            <Button size="small" startIcon={<RefreshIcon />} onClick={detectDeps}>
                                Recheck All
                            </Button>
                        </Box>
                    </>
                )}
            </SettingGroup>
        </>
    );
}

function DependencyRow({ dep, isInstalling, onInstall }: { dep: DependencyInfo; isInstalling: boolean; onInstall: () => void }) {
    const theme = useTheme();
    const canInstall = dep.status === 'missing' || dep.status === 'outdated';
    const isCuda = dep.id === 'cuda';

    return (
        <Paper
            elevation={0}
            sx={{
                p: 1.5, mb: 0.5,
                border: `1px solid ${theme.palette.divider}`,
                borderRadius: 1,
                display: 'flex',
                alignItems: 'center',
                gap: 1.5,
            }}
        >
            <DependencyStatusIcon status={isInstalling ? 'installing' : dep.status} />
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
                    startIcon={isInstalling ? <CircularProgress size={14} color="inherit" /> : <DownloadIcon />}
                    onClick={onInstall}
                    disabled={isInstalling}
                    sx={{ textTransform: 'none', fontSize: '0.75rem', whiteSpace: 'nowrap' }}
                >
                    {isInstalling ? 'Installing...' : dep.status === 'outdated' ? 'Update' : 'Install'}
                </Button>
            )}
            {canInstall && isCuda && (
                <Typography variant="caption" sx={{ color: theme.palette.text.disabled, fontStyle: 'italic' }}>
                    Manual install
                </Typography>
            )}
        </Paper>
    );
}

// ── Section: Raw Editor ──

function EditorSection() {
    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
            <SectionHeader
                title="Raw Editor"
                description="View and edit all settings as JSON, YAML, or TOML. Upload a file or edit directly, then apply."
            />
            <Box sx={{ flex: 1, minHeight: 0 }}>
                <SettingsEditor />
            </Box>
        </Box>
    );
}

// ── Section Map ──

const SECTION_RENDERERS: Record<SectionId, React.FC> = {
    appearance: AppearanceSection,
    connection: ConnectionSection,
    recording: RecordingSection,
    calibration: CalibrationSection,
    mocap: MocapSection,
    vmc: VMCSection,
    system: SystemSection,
    editor: EditorSection,
};

// ── Main Settings Page ──

export const SettingsPage: React.FC = () => {
    const theme = useTheme();
    const navigate = useNavigate();
    const [activeSection, setActiveSection] = useState<SectionId>('appearance');

    const SectionContent = SECTION_RENDERERS[activeSection];

    return (
        <Box
            sx={{
                width: '100%',
                height: '100%',
                display: 'flex',
                backgroundColor: theme.palette.mode === 'dark'
                    ? theme.palette.background.default
                    : theme.palette.grey[50],
                overflow: 'hidden',
            }}
        >
            {/* Left navigation panel */}
            <Paper
                elevation={0}
                sx={{
                    width: 240,
                    minWidth: 240,
                    height: '100%',
                    borderRight: `1px solid ${theme.palette.divider}`,
                    borderRadius: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                }}
            >
                {/* Settings header with back button */}
                <Box
                    sx={{
                        px: 2,
                        py: 1.5,
                        borderBottom: `1px solid ${theme.palette.divider}`,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 1,
                    }}
                >
                    <IconButton size="small" onClick={() => navigate('/')}>
                        <ArrowBackIcon sx={{ fontSize: 18 }} />
                    </IconButton>
                    <Typography variant="h6" sx={{ fontWeight: 700, fontSize: '1.1rem' }}>
                        Settings
                    </Typography>
                </Box>

                {/* Section list */}
                <List
                    sx={{
                        flex: 1,
                        overflowY: 'auto',
                        py: 1,
                    }}
                >
                    {SECTIONS.map((section) => (
                        <ListItemButton
                            key={section.id}
                            selected={activeSection === section.id}
                            onClick={() => setActiveSection(section.id)}
                            sx={{
                                mx: 1,
                                borderRadius: 1.5,
                                mb: 0.25,
                                py: 1,
                                '&.Mui-selected': {
                                    backgroundColor: theme.palette.mode === 'dark'
                                        ? 'rgba(255, 255, 255, 0.08)'
                                        : 'rgba(0, 0, 0, 0.06)',
                                    '&:hover': {
                                        backgroundColor: theme.palette.mode === 'dark'
                                            ? 'rgba(255, 255, 255, 0.12)'
                                            : 'rgba(0, 0, 0, 0.09)',
                                    },
                                },
                            }}
                        >
                            <ListItemIcon sx={{ minWidth: 36, color: activeSection === section.id ? theme.palette.primary.main : theme.palette.text.secondary }}>
                                {section.icon}
                            </ListItemIcon>
                            <ListItemText
                                primary={section.label}
                                primaryTypographyProps={{
                                    fontSize: '0.875rem',
                                    fontWeight: activeSection === section.id ? 600 : 400,
                                }}
                            />
                        </ListItemButton>
                    ))}
                </List>
            </Paper>

            {/* Right content area */}
            <Box
                sx={{
                    flex: 1,
                    height: '100%',
                    overflowY: activeSection === 'editor' ? 'hidden' : 'auto',
                    p: activeSection === 'editor' ? 2 : 4,
                    maxWidth: activeSection === 'editor' ? undefined : 800,
                    display: 'flex',
                    flexDirection: 'column',
                }}
            >
                <SectionContent />
            </Box>
        </Box>
    );
};

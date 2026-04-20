/**
 * RecordingBrowser — lists available recording sessions from the server,
 * with search filtering, multi-field sorting, and rich per-recording metadata.
 *
 * Standalone component: only depends on MUI + server URL helper.
 */
import React, {useCallback, useEffect, useMemo, useState} from 'react';
import {
    Box,
    Button,
    Chip,
    CircularProgress,
    Collapse,
    IconButton,
    InputAdornment,
    List,
    ListItem,
    ListItemButton,
    ListItemIcon,
    ListItemText,
    MenuItem,
    Select,
    type SelectChangeEvent,
    TextField,
    Tooltip,
    Typography,
    useTheme,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FolderIcon from '@mui/icons-material/Folder';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import RefreshIcon from '@mui/icons-material/Refresh';
import VideocamIcon from '@mui/icons-material/Videocam';
import StorageIcon from '@mui/icons-material/Storage';
import AccessTimeIcon from '@mui/icons-material/AccessTime';
import SearchIcon from '@mui/icons-material/Search';
import SortIcon from '@mui/icons-material/Sort';
import {serverUrls} from '@/constants/server-urls';
import {useTranslation} from 'react-i18next';
import {RecordingStatusSummary} from '@/types/recording-status';
import {RecordingStatusPanel} from '@/components/common/RecordingStatusPanel';
import {useRecordingStatus} from '@/hooks/useRecordingStatus';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Shape returned by GET /freemocap/playback/recordings */
interface RecordingEntry {
    name: string;
    path: string;
    video_count: number;
    total_size_bytes?: number;
    created_timestamp?: string;
    total_frames?: number;
    duration_seconds?: number;
    fps?: number;
    status_summary?: RecordingStatusSummary;
}

/** Shape passed up to the parent when a recording is loaded */
export interface LoadedVideo {
    videoId: string;
    filename: string;
    streamUrl: string;
    sizeBytes: number;
}

interface RecordingBrowserProps {
    onRecordingLoaded: (videos: LoadedVideo[], recordingPath: string, recordingFps?: number) => void;
    /** If set, automatically load this recording path on mount. */
    initialLoadPath?: string | null;
    /** Name/path of the recording currently loaded into the Playback view — highlighted in the list. */
    activeRecordingPath?: string | null;
}

type SortField = 'date' | 'name' | 'size' | 'cameras' | 'frames' | 'duration';
type SortDirection = 'asc' | 'desc';

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatBytes(bytes: number): string {
    if (bytes <= 0) return '0 B';
    const k = 1024;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(i > 1 ? 1 : 0)} ${units[i]}`;
}

function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    if (m >= 60) {
        const h = Math.floor(m / 60);
        const rm = m % 60;
        return `${h}h ${rm}m ${s}s`;
    }
    return `${m}m ${s}s`;
}

/**
 * Try to parse an ISO-like timestamp from a recording folder name.
 * Handles patterns like:
 *   2026-02-18_09-24-12_GMT-5
 *   2026-02-18T09_24_12
 *   2026-02-18
 */
function parseTimestampFromName(name: string): Date | null {
    // Full datetime: 2026-02-18_09-24-12 or 2026-02-18T09:24:12
    const fullMatch = name.match(
        /(\d{4})-(\d{2})-(\d{2})[T_](\d{2})[_:\-](\d{2})[_:\-](\d{2})/
    );
    if (fullMatch) {
        const [, y, mo, d, h, mi, s] = fullMatch;
        return new Date(+y, +mo - 1, +d, +h, +mi, +s);
    }
    // Date only: 2026-02-18
    const dateMatch = name.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (dateMatch) {
        const [, y, mo, d] = dateMatch;
        return new Date(+y, +mo - 1, +d);
    }
    return null;
}

function formatRelativeTime(date: Date): string {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    if (diffHr < 24) return `${diffHr}h ago`;
    const diffDays = Math.floor(diffHr / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
    return date.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
    });
}

// ---------------------------------------------------------------------------
// Sort helpers
// ---------------------------------------------------------------------------

function getSortValue(rec: RecordingEntry, field: SortField): number | string {
    switch (field) {
        case 'date': {
            const d = parseTimestampFromName(rec.name);
            return d ? d.getTime() : 0;
        }
        case 'name':
            return rec.name.toLowerCase();
        case 'size':
            return rec.total_size_bytes ?? 0;
        case 'cameras':
            return rec.video_count;
        case 'frames':
            return rec.total_frames ?? 0;
        case 'duration':
            return rec.duration_seconds ?? 0;
    }
}

function compareRecordings(
    a: RecordingEntry,
    b: RecordingEntry,
    field: SortField,
    direction: SortDirection,
): number {
    const va = getSortValue(a, field);
    const vb = getSortValue(b, field);
    let cmp: number;
    if (typeof va === 'string' && typeof vb === 'string') {
        cmp = va.localeCompare(vb);
    } else {
        cmp = (va as number) - (vb as number);
    }
    return direction === 'desc' ? -cmp : cmp;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MONO_FONT = '"JetBrains Mono", "Fira Code", "SF Mono", "Cascadia Code", monospace';
const ACCENT_BLUE = '#29b6f6';
const ACCENT_GREEN = '#00ff88';

const SORT_OPTIONS: { value: SortField; labelKey: string }[] = [
    { value: 'date', labelKey: 'date' },
    { value: 'name', labelKey: 'name' },
    { value: 'size', labelKey: 'size' },
    { value: 'cameras', labelKey: 'cameras' },
    { value: 'frames', labelKey: 'frames' },
    { value: 'duration', labelKey: 'duration' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export const RecordingBrowser: React.FC<RecordingBrowserProps> = ({ onRecordingLoaded, initialLoadPath, activeRecordingPath }) => {
    const theme = useTheme();
    const { t } = useTranslation();
    const isDark = theme.palette.mode === 'dark';

    // Data state
    const [recordings, setRecordings] = useState<RecordingEntry[]>([]);
    const [isLoadingList, setIsLoadingList] = useState(false);
    const [isLoadingRecording, setIsLoadingRecording] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [loadingPath, setLoadingPath] = useState<string | null>(null);

    // Manual path input
    const [manualPath, setManualPath] = useState('');

    // Filter / sort
    const [filterText, setFilterText] = useState('');
    const [sortField, setSortField] = useState<SortField>('date');
    const [sortDir, setSortDir] = useState<SortDirection>('desc');

    // -----------------------------------------------------------------------
    // Fetch the list of recordings from the server
    // -----------------------------------------------------------------------
    const fetchRecordings = useCallback(async () => {
        setIsLoadingList(true);
        setError(null);
        try {
            const response = await fetch(serverUrls.endpoints.playbackRecordings);
            if (!response.ok) {
                throw new Error(`Failed to fetch recordings: ${response.statusText}`);
            }
            const data: RecordingEntry[] = await response.json();
            setRecordings(data);
        } catch (e) {
            setError(e instanceof Error ? e.message : t('failedToFetch'));
        } finally {
            setIsLoadingList(false);
        }
    }, []);

    useEffect(() => {
        fetchRecordings();
    }, [fetchRecordings]);

    // -----------------------------------------------------------------------
    // Apply filter + sort
    // -----------------------------------------------------------------------
    const filteredSorted = useMemo(() => {
        let result = recordings;

        // Text filter
        if (filterText.trim()) {
            const q = filterText.trim().toLowerCase();
            result = result.filter((r) => r.name.toLowerCase().includes(q));
        }

        // Sort
        return [...result].sort((a, b) => compareRecordings(a, b, sortField, sortDir));
    }, [recordings, filterText, sortField, sortDir]);

    // -----------------------------------------------------------------------
    // Load a specific recording
    // -----------------------------------------------------------------------
    const loadRecording = useCallback(
        async (recordingPath: string) => {
            setIsLoadingRecording(true);
            setLoadingPath(recordingPath);
            setError(null);

            try {
                // Determine recording ID (name)
                const rec = recordings.find((r) => r.path === recordingPath);
                const recName = rec ? rec.name : recordingPath.split(/[\\/]/).pop() || recordingPath;

                const response = await fetch(serverUrls.endpoints.playbackVideos(recName));

                if (!response.ok) {
                    const detail = await response
                        .json()
                        .catch(() => ({ detail: response.statusText }));
                    throw new Error(detail.detail || response.statusText);
                }

                const data = await response.json();
                const baseUrl = serverUrls.getHttpUrl();

                const videos: LoadedVideo[] = data.map(
                    (v: {
                        video_id: string;
                        filename: string;
                        stream_url: string;
                        size_bytes: number;
                    }) => ({
                        videoId: v.video_id,
                        filename: v.filename,
                        streamUrl: `${baseUrl}${v.stream_url}`,
                        sizeBytes: v.size_bytes,
                    }),
                );

                const recFps = rec?.fps ?? undefined;

                // Send recName as the recording path to identify it successfully in playbackpage
                onRecordingLoaded(videos, recName, recFps);
            } catch (e) {
                setError(e instanceof Error ? e.message : 'Failed to load recording');
            } finally {
                setIsLoadingRecording(false);
                setLoadingPath(null);
            }
        },
        [onRecordingLoaded, recordings],
    );

    // Auto-load a recording if initialLoadPath is provided
    const [didAutoLoad, setDidAutoLoad] = useState(false);
    useEffect(() => {
        if (initialLoadPath && !didAutoLoad) {
            setDidAutoLoad(true);
            loadRecording(initialLoadPath);
        }
    }, [initialLoadPath, didAutoLoad, loadRecording]);

    const handleLoadManualPath = useCallback(() => {
        const trimmed = manualPath.trim();
        if (trimmed) loadRecording(trimmed);
    }, [manualPath, loadRecording]);

    // -----------------------------------------------------------------------
    // Sort controls
    // -----------------------------------------------------------------------
    const handleSortFieldChange = (e: SelectChangeEvent) => {
        setSortField(e.target.value as SortField);
    };

    const toggleSortDir = () => {
        setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'));
    };

    // -----------------------------------------------------------------------
    // Render
    // -----------------------------------------------------------------------
    return (
        <Box
            sx={{
                display: 'flex',
                flexDirection: 'column',
                gap: 2,
                p: 2,
                height: '100%',
                overflow: 'hidden',
            }}
        >
            {/* ── Manual path input ── */}
            <Box sx={{ display: 'flex', gap: 1, alignItems: 'flex-start' }}>
                <TextField
                    fullWidth
                    size="small"
                    label={t("recordingFolderPath")}
                    placeholder="~/freemocap_data/recordings/2024-01-01..."
                    value={manualPath}
                    onChange={(e) => setManualPath(e.target.value)}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') handleLoadManualPath();
                    }}
                    disabled={isLoadingRecording}
                    sx={{ '& input': { fontFamily: MONO_FONT, fontSize: '0.85rem' } }}
                />
                <Button
                    variant="contained"
                    onClick={handleLoadManualPath}
                    disabled={!manualPath.trim() || isLoadingRecording}
                    startIcon={
                        isLoadingRecording && !loadingPath ? (
                            <CircularProgress size={16} />
                        ) : (
                            <PlayArrowIcon />
                        )
                    }
                    sx={{
                        whiteSpace: 'nowrap',
                        backgroundColor: isDark ? '#4caf50' : undefined,
                        color: isDark ? '#fff' : undefined,
                        '&:hover': { backgroundColor: isDark ? '#66bb6a' : undefined },
                    }}
                >
                    {t('load')}
                </Button>
            </Box>

            {/* ── Error ── */}
            {error && (
                <Typography color="error" variant="body2" sx={{ px: 1 }}>
                    {error}
                </Typography>
            )}

            {/* ── Header bar: title, filter, sort, refresh ── */}
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 1,
                }}
            >
                {/* Left: title + count */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    <Typography
                        variant="subtitle2"
                        sx={{
                            color: theme.palette.text.primary,
                            fontWeight: 600,
                        }}
                    >
                        {t('recordings')}
                    </Typography>
                    {recordings.length > 0 && (
                        <Chip
                            label={
                                filterText
                                    ? `${filteredSorted.length} / ${recordings.length}`
                                    : String(recordings.length)
                            }
                            size="small"
                            variant="outlined"
                            sx={{
                                height: 20,
                                fontSize: '0.7rem',
                                borderColor: isDark ? 'rgba(255,255,255,0.2)' : undefined,
                                color: isDark ? '#b3b9c6' : undefined,
                            }}
                        />
                    )}
                </Box>

                {/* Right: filter + sort + refresh */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                    {/* Search filter */}
                    <TextField
                        size="small"
                        placeholder={t("filter")}
                        value={filterText}
                        onChange={(e) => setFilterText(e.target.value)}
                        InputProps={{
                            startAdornment: (
                                <InputAdornment position="start">
                                    <SearchIcon
                                        sx={{
                                            fontSize: 16,
                                            color: isDark
                                                ? 'rgba(255,255,255,0.4)'
                                                : 'rgba(0,0,0,0.4)',
                                        }}
                                    />
                                </InputAdornment>
                            ),
                        }}
                        sx={{
                            width: 160,
                            '& input': { fontSize: '0.8rem', py: 0.5 },
                        }}
                    />

                    {/* Sort field dropdown */}
                    <Select
                        value={sortField}
                        onChange={handleSortFieldChange}
                        size="small"
                        variant="outlined"
                        sx={{
                            minWidth: 100,
                            '& .MuiSelect-select': {
                                py: 0.4,
                                fontSize: '0.75rem',
                                color: isDark ? '#b3b9c6' : undefined,
                            },
                            '& .MuiOutlinedInput-notchedOutline': {
                                borderColor: isDark
                                    ? 'rgba(255,255,255,0.2)'
                                    : undefined,
                            },
                            '& .MuiSvgIcon-root': {
                                color: isDark
                                    ? 'rgba(255,255,255,0.4)'
                                    : undefined,
                            },
                        }}
                    >
                        {SORT_OPTIONS.map((opt) => (
                            <MenuItem key={opt.value} value={opt.value}>
                                {t(opt.labelKey)}
                            </MenuItem>
                        ))}
                    </Select>

                    {/* Sort direction toggle */}
                    <Tooltip
                        title={`Sort ${sortDir === 'desc' ? 'newest first' : 'oldest first'} — click to toggle`}
                    >
                        <IconButton
                            size="small"
                            onClick={toggleSortDir}
                            sx={{
                                color: isDark ? '#b3b9c6' : theme.palette.text.secondary,
                            }}
                        >
                            <SortIcon
                                sx={{
                                    fontSize: 18,
                                    transform: sortDir === 'asc' ? 'scaleY(-1)' : 'none',
                                    transition: 'transform 0.2s ease',
                                }}
                            />
                        </IconButton>
                    </Tooltip>

                    {/* Refresh */}
                    <Button
                        size="small"
                        startIcon={<RefreshIcon />}
                        onClick={fetchRecordings}
                        disabled={isLoadingList}
                        sx={{ color: isDark ? '#b3b9c6' : undefined }}
                    >
                        {t('refresh')}
                    </Button>
                </Box>
            </Box>

            {/* ── Recording list ── */}
            {isLoadingList ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                    <CircularProgress size={24} sx={{ color: ACCENT_BLUE }} />
                </Box>
            ) : filteredSorted.length === 0 ? (
                <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ textAlign: 'center', py: 4 }}
                >
                    {recordings.length === 0
                        ? t('noRecordingsFound')
                        : 'No recordings match your filter.'}
                </Typography>
            ) : (
                <List
                    dense
                    sx={{
                        flex: 1,
                        overflow: 'auto',
                        border: `1px solid ${theme.palette.divider}`,
                        borderRadius: 1,
                        '& .MuiListItemButton-root + .MuiListItemButton-root': {
                            borderTop: `1px solid ${theme.palette.divider}`,
                        },
                    }}
                >
                    {filteredSorted.map((rec) => (
                        <RecordingRow
                            key={rec.path}
                            rec={rec}
                            isLoading={loadingPath === rec.path}
                            isAnyLoading={isLoadingRecording}
                            isDark={isDark}
                            isActive={!!activeRecordingPath && (activeRecordingPath === rec.name || activeRecordingPath === rec.path)}
                            onClick={() => loadRecording(rec.path)}
                            recordingsRootPath={rec.path.slice(0, Math.max(rec.path.lastIndexOf('/'), rec.path.lastIndexOf('\\'))) || null}
                        />
                    ))}
                </List>
            )}
        </Box>
    );
};

// ---------------------------------------------------------------------------
// RecordingRow — a single recording in the list
// ---------------------------------------------------------------------------

interface RecordingRowProps {
    rec: RecordingEntry;
    isLoading: boolean;
    isAnyLoading: boolean;
    isDark: boolean;
    isActive: boolean;
    onClick: () => void;
    recordingsRootPath: string | null;
}

const RecordingRow: React.FC<RecordingRowProps> = React.memo(
    ({ rec, isLoading, isAnyLoading, isDark, isActive, onClick, recordingsRootPath }) => {
        const theme = useTheme();
        const parsedDate = parseTimestampFromName(rec.name);
        const { t } = useTranslation();
        const [expanded, setExpanded] = useState(false);

        const {
            status: detailedStatus,
            isLoading: statusLoading,
            error: statusError,
            refresh: refreshStatus,
        } = useRecordingStatus(expanded ? rec.name : null, {
            autoFetch: expanded,
            recordingParentDirectory: recordingsRootPath,
        });

        const summary = rec.status_summary;
        const ready = summary?.blender_export_ready ?? false;
        const stagesComplete = summary?.stages_complete ?? 0;
        const stagesTotal = summary?.stages_total ?? 0;

        const toggleExpand = (e: React.MouseEvent): void => {
            e.stopPropagation();
            setExpanded((v) => !v);
        };

        return (
            <ListItem
                disablePadding
                sx={{
                    flexDirection: 'column',
                    alignItems: 'stretch',
                    ...(isActive && {
                        backgroundColor: isDark ? 'rgba(41,182,246,0.12)' : 'rgba(41,182,246,0.10)',
                        borderLeft: `3px solid ${ACCENT_BLUE}`,
                    }),
                }}
            >
                <Box sx={{display: 'flex', alignItems: 'stretch'}}>
                <ListItemButton
                    onClick={onClick}
                    disabled={isAnyLoading}
                    sx={{
                        py: 1.25,
                        px: 2,
                        flex: 1,
                        opacity: isAnyLoading && !isLoading ? 0.5 : 1,
                    }}
                >
                {/* Folder icon or spinner */}
                <ListItemIcon sx={{ minWidth: 36 }}>
                    {isLoading ? (
                        <CircularProgress size={20} sx={{ color: ACCENT_BLUE }} />
                    ) : (
                        <FolderIcon
                            fontSize="small"
                            sx={{
                                color: isDark
                                    ? ACCENT_BLUE
                                    : theme.palette.primary.main,
                            }}
                        />
                    )}
                </ListItemIcon>

                <ListItemText
                    disableTypography
                    primary={
                        <Box sx={{display: 'flex', alignItems: 'center', gap: 1, mb: 0.5}}>
                            <Typography
                                variant="body2"
                                sx={{
                                    fontFamily: MONO_FONT,
                                    fontWeight: 600,
                                    fontSize: '0.85rem',
                                    color: isActive
                                        ? (isDark ? ACCENT_BLUE : theme.palette.primary.main)
                                        : theme.palette.text.primary,
                                }}
                            >
                                {rec.name}
                            </Typography>
                            {isActive && (
                                <Chip
                                    size="small"
                                    icon={<PlayArrowIcon sx={{fontSize: '12px !important'}}/>}
                                    label="loaded in playback"
                                    sx={{
                                        height: 18,
                                        fontSize: '0.65rem',
                                        fontFamily: MONO_FONT,
                                        backgroundColor: isDark ? `${ACCENT_BLUE}22` : 'rgba(41,182,246,0.15)',
                                        color: isDark ? ACCENT_BLUE : theme.palette.primary.main,
                                        border: `1px solid ${isDark ? `${ACCENT_BLUE}55` : 'rgba(41,182,246,0.4)'}`,
                                        '& .MuiChip-icon': {color: 'inherit'},
                                        '& .MuiChip-label': {px: 0.75},
                                    }}
                                />
                            )}
                        </Box>
                    }
                    secondary={
                        <Box
                            sx={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: 1.5,
                                alignItems: 'center',
                            }}
                        >
                            {/* Camera count */}
                            <StatBadge
                                icon={
                                    <VideocamIcon
                                        sx={{
                                            fontSize: 14,
                                            color: theme.palette.text.secondary,
                                        }}
                                    />
                                }
                                label={`${rec.video_count} cam${rec.video_count !== 1 ? 's' : ''}`}
                                tooltip="Camera streams"
                            />

                            {/* Size */}
                            {rec.total_size_bytes != null &&
                                rec.total_size_bytes > 0 && (
                                    <StatBadge
                                        icon={
                                            <StorageIcon
                                                sx={{
                                                    fontSize: 14,
                                                    color: theme.palette.text
                                                        .secondary,
                                                }}
                                            />
                                        }
                                        label={formatBytes(rec.total_size_bytes)}
                                        tooltip="Total size on disk"
                                    />
                                )}

                            {/* Duration */}
                            {rec.duration_seconds != null &&
                                rec.duration_seconds > 0 && (
                                    <StatBadge
                                        icon={
                                            <AccessTimeIcon
                                                sx={{
                                                    fontSize: 14,
                                                    color: theme.palette.text
                                                        .secondary,
                                                }}
                                            />
                                        }
                                        label={formatDuration(rec.duration_seconds)}
                                        tooltip="Recording duration"
                                    />
                                )}

                            {/* Frame count chip */}
                            {rec.total_frames != null && rec.total_frames > 0 && (
                                <Tooltip title={t("frameCountPerCamera")}>
                                    <Chip
                                        label={`${rec.total_frames.toLocaleString()} frames`}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                            height: 18,
                                            fontSize: '0.65rem',
                                            fontFamily: MONO_FONT,
                                            '& .MuiChip-label': { px: 0.75 },
                                            borderColor: isDark
                                                ? `${ACCENT_GREEN}44`
                                                : undefined,
                                            color: isDark
                                                ? ACCENT_GREEN
                                                : undefined,
                                        }}
                                    />
                                </Tooltip>
                            )}

                            {/* FPS chip */}
                            {rec.fps != null && rec.fps > 0 && (
                                <Tooltip title={t("recordingCaptureFps")}>
                                    <Chip
                                        label={`${rec.fps} fps`}
                                        size="small"
                                        variant="outlined"
                                        sx={{
                                            height: 18,
                                            fontSize: '0.65rem',
                                            fontFamily: MONO_FONT,
                                            '& .MuiChip-label': { px: 0.75 },
                                            borderColor: isDark
                                                ? `${ACCENT_BLUE}44`
                                                : undefined,
                                            color: isDark
                                                ? ACCENT_BLUE
                                                : theme.palette.info.main,
                                        }}
                                    />
                                </Tooltip>
                            )}

                            {/* Relative time */}
                            {parsedDate && (
                                <Tooltip title={parsedDate.toLocaleString()}>
                                    <Typography
                                        variant="caption"
                                        sx={{
                                            color: theme.palette.text.disabled,
                                            fontStyle: 'italic',
                                        }}
                                    >
                                        {formatRelativeTime(parsedDate)}
                                    </Typography>
                                </Tooltip>
                            )}

                            {/* Status summary */}
                            {summary && (
                                <Tooltip
                                    title={
                                        ready
                                            ? 'All pipeline stages complete — ready for Blender'
                                            : `${stagesComplete}/${stagesTotal} pipeline stages complete`
                                    }
                                >
                                    <Chip
                                        size="small"
                                        label={
                                            ready
                                                ? 'Blender ready'
                                                : `${stagesComplete}/${stagesTotal} stages`
                                        }
                                        color={ready ? 'success' : 'default'}
                                        icon={ready ? <CheckCircleIcon/> : undefined}
                                        variant={ready ? 'filled' : 'outlined'}
                                        sx={{height: 18, fontSize: '0.65rem', '& .MuiChip-label': {px: 0.75}}}
                                    />
                                </Tooltip>
                            )}
                        </Box>
                    }
                />
                </ListItemButton>
                <Tooltip title={expanded ? 'Hide folder detail' : 'Show folder detail'}>
                    <IconButton
                        size="small"
                        onClick={toggleExpand}
                        sx={{
                            mr: 1,
                            alignSelf: 'center',
                            transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s ease',
                        }}
                    >
                        <ExpandMoreIcon fontSize="small"/>
                    </IconButton>
                </Tooltip>
                </Box>
                <Collapse in={expanded} unmountOnExit>
                    <Box sx={{px: 2, pb: 2}}>
                        <RecordingStatusPanel
                            status={detailedStatus}
                            isLoading={statusLoading}
                            error={statusError}
                            onRefresh={refreshStatus}
                        />
                    </Box>
                </Collapse>
            </ListItem>
        );
    },
);

RecordingRow.displayName = 'RecordingRow';

// ---------------------------------------------------------------------------
// StatBadge — tiny icon + label used in the secondary line
// ---------------------------------------------------------------------------

interface StatBadgeProps {
    icon: React.ReactNode;
    label: string;
    tooltip: string;
}

const StatBadge: React.FC<StatBadgeProps> = ({ icon, label, tooltip }) => (
    <Tooltip title={tooltip}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            {icon}
            <Typography variant="caption" color="text.secondary">
                {label}
            </Typography>
        </Box>
    </Tooltip>
);

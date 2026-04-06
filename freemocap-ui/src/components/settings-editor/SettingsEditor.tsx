import React, { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import {
    Box,
    Button,
    ButtonGroup,
    Alert,
    Snackbar,
    Tooltip,
    Divider,
    CircularProgress,
} from '@mui/material';
import { useTheme } from '@mui/material/styles';
import Editor, { OnMount } from '@monaco-editor/react';
import UploadFileIcon from '@mui/icons-material/UploadFile';
import DownloadIcon from '@mui/icons-material/Download';
import CheckIcon from '@mui/icons-material/Check';
import RestoreIcon from '@mui/icons-material/Restore';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import {
    useAppDispatch,
    useAppSelector,
    themeModeSet,
    recordingDirectoryChanged,
    configUpdated,
    selectServerSettings,
} from '@/store';
import {
    mocapDetectorConfigReplaced,
    skeletonFilterConfigReplaced,
    updateMocapConfigOnServer,
} from '@/store/slices/mocap';
import {calibrationConfigUpdated, updateCalibrationConfigOnServer } from '@/store/slices/calibration';
import { ThemeMode } from '@/store/slices/theme/theme-types';
import {
    serialize,
    deserialize,
    convertFormat,
    SerializationFormat,
    FORMAT_EXTENSIONS,
    FORMAT_MIME_TYPES,
    FORMAT_MONACO_LANGUAGES,
} from './format-converters';
import {useServer} from "@/services";

// ── Aggregated settings shape (config-only, no runtime state) ──

interface AggregatedSettings {
    appearance: {
        mode: string;
    };
    recording: {
        recording_directory: string;
        use_delay_start: boolean;
        delay_seconds: number;
        use_timestamp: boolean;
        use_increment: boolean;
        current_increment: number;
        base_name: string;
        recording_tag: string;
        create_subfolder: boolean;
        custom_subfolder_name: string;
    };
    calibration: {
        live_track_charuco: boolean;
        charuco_board_x_squares: number;
        charuco_board_y_squares: number;
        charuco_square_length: number;
        min_shared_views_per_camera: number;
        auto_stop_on_min_view_count: boolean;
        solver_method: string;
        use_groundplane: boolean;
    };
    mocap: {
        detector: Record<string, unknown>;
        skeleton_filter: Record<string, unknown>;
    };
    // vmc: {
    //     enabled: boolean;
    //     host: string;
    //     port: number;
    // };
}

// ── Hook: gather current settings into a flat config object ──

function useAggregatedSettings(): AggregatedSettings {
    const themeMode = useAppSelector(state => state.theme.mode);
    const recording = useAppSelector(state => state.recording);
    const calibration = useAppSelector(state => state.calibration.config);
    const mocap = useAppSelector(state => state.mocap.config);
    const serverSettings = useAppSelector(selectServerSettings);

    return useMemo((): AggregatedSettings => ({
        appearance: {
            mode: themeMode,
        },
        recording: {
            recording_directory: recording.recordingDirectory,
            use_delay_start: recording.config.useDelayStart,
            delay_seconds: recording.config.delaySeconds,
            use_timestamp: recording.config.useTimestamp,
            use_increment: recording.config.useIncrement,
            current_increment: recording.config.currentIncrement,
            base_name: recording.config.baseName,
            recording_tag: recording.config.recordingTag,
            create_subfolder: recording.config.createSubfolder,
            custom_subfolder_name: recording.config.customSubfolderName,
        },
        calibration: {
            live_track_charuco: calibration.liveTrackCharuco,
            charuco_board_x_squares: calibration.charucoBoardXSquares,
            charuco_board_y_squares: calibration.charucoBoardYSquares,
            charuco_square_length: calibration.charucoSquareLength,
            min_shared_views_per_camera: calibration.minSharedViewsPerCamera,
            auto_stop_on_min_view_count: calibration.autoStopOnMinViewCount,
            solver_method: calibration.solverMethod,
            use_groundplane: calibration.useGroundplane,
        },
        mocap: {
            detector: mocap.detector as unknown as Record<string, unknown>,
            skeleton_filter: mocap.skeleton_filter as unknown as Record<string, unknown>,
        },
        // vmc: {
        //     enabled: serverSettings?.vmc?.enabled ?? false,
        //     host: serverSettings?.vmc?.host ?? '127.0.0.1',
        //     port: serverSettings?.vmc?.port ?? 39539,
        // },
    }), [themeMode, recording, calibration, mocap, serverSettings]);
}

// ── Apply parsed settings back to the Redux stores ──

function useApplySettings() {
    const dispatch = useAppDispatch();
    const { send, isConnected } = useServer();

    return useCallback((parsed: Record<string, unknown>) => {
        const settings = parsed as unknown as Partial<AggregatedSettings>;

        // Appearance
        if (settings.appearance && typeof settings.appearance.mode === 'string') {
            const mode = settings.appearance.mode;
            if (mode === 'dark' || mode === 'light') {
                dispatch(themeModeSet(mode as ThemeMode));
            } else {
                throw new Error(`Invalid appearance.mode: "${mode}" (must be "dark" or "light")`);
            }
        }

        // Recording
        if (settings.recording) {
            const rec = settings.recording;
            if (typeof rec.recording_directory === 'string') {
                dispatch(recordingDirectoryChanged(rec.recording_directory));
            }
            dispatch(configUpdated({
                useDelayStart: rec.use_delay_start,
                delaySeconds: rec.delay_seconds,
                useTimestamp: rec.use_timestamp,
                useIncrement: rec.use_increment,
                currentIncrement: rec.current_increment,
                baseName: rec.base_name,
                recordingTag: rec.recording_tag,
                createSubfolder: rec.create_subfolder,
                customSubfolderName: rec.custom_subfolder_name,
            }));
        }

        // Calibration
        if (settings.calibration) {
            const cal = settings.calibration;
            dispatch(calibrationConfigUpdated({
                liveTrackCharuco: cal.live_track_charuco,
                charucoBoardXSquares: cal.charuco_board_x_squares,
                charucoBoardYSquares: cal.charuco_board_y_squares,
                charucoSquareLength: cal.charuco_square_length,
                minSharedViewsPerCamera: cal.min_shared_views_per_camera,
                autoStopOnMinViewCount: cal.auto_stop_on_min_view_count,
                solverMethod: cal.solver_method as 'anipose' | 'pyceres',
                useGroundplane: cal.use_groundplane,
            }));
            dispatch(updateCalibrationConfigOnServer());
        }

        // Mocap
        if (settings.mocap) {
            if (settings.mocap.detector) {
                dispatch(mocapDetectorConfigReplaced(settings.mocap.detector as any));
            }
            if (settings.mocap.skeleton_filter) {
                dispatch(skeletonFilterConfigReplaced(settings.mocap.skeleton_filter as any));
            }
            dispatch(updateMocapConfigOnServer());
        }

        // VMC (patched via WebSocket) - currently disabled
        // if (settings.vmc && isConnected) {
        //     send({
        //         message_type: 'settings/patch',
        //         patch: {
        //             vmc: {
        //                 enabled: settings.vmc.enabled,
        //                 host: settings.vmc.host,
        //                 port: settings.vmc.port,
        //             },
        //         },
        //     });
        // }
    }, [dispatch, send, isConnected]);
}

// ── Format toggle button ──

function FormatButton({
    format,
    active,
    onClick,
}: {
    format: SerializationFormat;
    active: boolean;
    onClick: () => void;
}) {
    return (
        <Button
            size="small"
            variant={active ? 'contained' : 'outlined'}
            onClick={onClick}
            sx={{
                textTransform: 'uppercase',
                fontWeight: 700,
                fontSize: '0.7rem',
                minWidth: 56,
                letterSpacing: 0.8,
            }}
        >
            {format}
        </Button>
    );
}

// ── Main editor component ──

export const SettingsEditor: React.FC = () => {
    const theme = useTheme();
    const aggregated = useAggregatedSettings();
    const applySettings = useApplySettings();

    const [format, setFormat] = useState<SerializationFormat>('json');
    const [editorContent, setEditorContent] = useState<string>('');
    const [hasEdits, setHasEdits] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [snackbar, setSnackbar] = useState<{ message: string; severity: 'success' | 'error' } | null>(null);

    const editorRef = useRef<any>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Serialize current settings whenever aggregated state or format changes (only if no pending edits)
    const serializedFromStore = useMemo(
        () => serialize(aggregated as unknown as Record<string, unknown>, format),
        [aggregated, format],
    );

    // Sync editor content from store when there are no pending edits
    useEffect(() => {
        if (!hasEdits) {
            setEditorContent(serializedFromStore);
        }
    }, [serializedFromStore, hasEdits]);

    // Initialize editor on first mount
    useEffect(() => {
        setEditorContent(serialize(aggregated as unknown as Record<string, unknown>, format));
        // Only run on mount
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleEditorMount: OnMount = useCallback((editor) => {
        editorRef.current = editor;
    }, []);

    const handleEditorChange = useCallback((value: string | undefined) => {
        if (value === undefined) return;
        setEditorContent(value);
        setHasEdits(true);
        setError(null);
    }, []);

    // Format switching — convert current content to new format
    const handleFormatChange = useCallback((newFormat: SerializationFormat) => {
        if (newFormat === format) return;
        try {
            const converted = convertFormat(editorContent, format, newFormat);
            setEditorContent(converted);
            setFormat(newFormat);
            setError(null);
        } catch (err) {
            setError(`Cannot convert to ${newFormat.toUpperCase()}: ${err instanceof Error ? err.message : String(err)}`);
        }
    }, [editorContent, format]);

    // Reset editor to current store state
    const handleReset = useCallback(() => {
        const fresh = serialize(aggregated as unknown as Record<string, unknown>, format);
        setEditorContent(fresh);
        setHasEdits(false);
        setError(null);
    }, [aggregated, format]);

    // Apply edits to store
    const handleApply = useCallback(() => {
        try {
            const parsed = deserialize(editorContent, format);
            applySettings(parsed);
            setHasEdits(false);
            setError(null);
            setSnackbar({ message: 'Settings applied successfully', severity: 'success' });
        } catch (err) {
            const message = err instanceof Error ? err.message : String(err);
            setError(`Failed to apply: ${message}`);
            setSnackbar({ message: `Failed to apply settings: ${message}`, severity: 'error' });
        }
    }, [editorContent, format, applySettings]);

    // Copy to clipboard
    const handleCopy = useCallback(async () => {
        try {
            await navigator.clipboard.writeText(editorContent);
            setSnackbar({ message: 'Copied to clipboard', severity: 'success' });
        } catch {
            setSnackbar({ message: 'Failed to copy to clipboard', severity: 'error' });
        }
    }, [editorContent]);

    // Download as file
    const handleDownload = useCallback(() => {
        const blob = new Blob([editorContent], { type: FORMAT_MIME_TYPES[format] });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `freemocap-settings${FORMAT_EXTENSIONS[format]}`;
        a.click();
        URL.revokeObjectURL(url);
    }, [editorContent, format]);

    // Upload from file
    const handleUploadClick = useCallback(() => {
        fileInputRef.current?.click();
    }, []);

    const handleFileSelected = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        // Detect format from file extension
        const ext = file.name.split('.').pop()?.toLowerCase();
        let detectedFormat: SerializationFormat = format;
        if (ext === 'json') detectedFormat = 'json';
        else if (ext === 'yaml' || ext === 'yml') detectedFormat = 'yaml';
        else if (ext === 'toml') detectedFormat = 'toml';

        const reader = new FileReader();
        reader.onload = (event) => {
            const text = event.target?.result;
            if (typeof text !== 'string') {
                setError('Failed to read file');
                return;
            }
            try {
                // Validate by parsing
                deserialize(text, detectedFormat);
                setFormat(detectedFormat);
                setEditorContent(text);
                setHasEdits(true);
                setError(null);
                setSnackbar({ message: `Loaded ${file.name} (${detectedFormat.toUpperCase()})`, severity: 'success' });
            } catch (err) {
                setError(`Invalid ${detectedFormat.toUpperCase()} in ${file.name}: ${err instanceof Error ? err.message : String(err)}`);
            }
        };
        reader.onerror = () => {
            setError(`Failed to read file: ${file.name}`);
        };
        reader.readAsText(file);

        // Reset the input so the same file can be re-selected
        e.target.value = '';
    }, [format]);

    const isDark = theme.palette.mode === 'dark';

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 1.5 }}>
            {/* Toolbar */}
            <Box
                sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 1,
                }}
            >
                {/* Format selector */}
                <ButtonGroup size="small" variant="outlined">
                    <FormatButton format="json" active={format === 'json'} onClick={() => handleFormatChange('json')} />
                    <FormatButton format="yaml" active={format === 'yaml'} onClick={() => handleFormatChange('yaml')} />
                    <FormatButton format="toml" active={format === 'toml'} onClick={() => handleFormatChange('toml')} />
                </ButtonGroup>

                {/* Action buttons */}
                <Box sx={{ display: 'flex', gap: 0.75 }}>
                    <Tooltip title="Copy to clipboard">
                        <Button size="small" variant="outlined" onClick={handleCopy} sx={{ minWidth: 0, px: 1 }}>
                            <ContentCopyIcon sx={{ fontSize: 16 }} />
                        </Button>
                    </Tooltip>
                    <Tooltip title="Upload settings file (.json, .yaml, .toml)">
                        <Button size="small" variant="outlined" onClick={handleUploadClick} startIcon={<UploadFileIcon sx={{ fontSize: 16 }} />}>
                            Upload
                        </Button>
                    </Tooltip>
                    <Tooltip title={`Download as ${format.toUpperCase()}`}>
                        <Button size="small" variant="outlined" onClick={handleDownload} startIcon={<DownloadIcon sx={{ fontSize: 16 }} />}>
                            Download
                        </Button>
                    </Tooltip>

                    <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

                    <Tooltip title="Reset to current app state">
                        <span>
                            <Button
                                size="small"
                                variant="outlined"
                                onClick={handleReset}
                                disabled={!hasEdits}
                                startIcon={<RestoreIcon sx={{ fontSize: 16 }} />}
                            >
                                Reset
                            </Button>
                        </span>
                    </Tooltip>
                    <Tooltip title="Apply edits to app">
                        <span>
                            <Button
                                size="small"
                                variant="contained"
                                color="success"
                                onClick={handleApply}
                                disabled={!hasEdits}
                                startIcon={<CheckIcon sx={{ fontSize: 16 }} />}
                            >
                                Apply
                            </Button>
                        </span>
                    </Tooltip>
                </Box>
            </Box>

            {/* Status bar */}
            {hasEdits && (
                <Alert severity="info" sx={{ py: 0, fontSize: '0.75rem' }}>
                    You have unsaved edits. Click <strong>Apply</strong> to push changes to the app, or <strong>Reset</strong> to discard.
                </Alert>
            )}
            {error && (
                <Alert severity="error" sx={{ py: 0, fontSize: '0.75rem' }}>
                    {error}
                </Alert>
            )}

            {/* Monaco Editor */}
            <Box
                sx={{
                    flex: 1,
                    minHeight: 400,
                    border: `1px solid ${theme.palette.divider}`,
                    borderRadius: 1,
                    overflow: 'hidden',
                }}
            >
                <Editor
                    height="100%"
                    language={FORMAT_MONACO_LANGUAGES[format]}
                    value={editorContent}
                    theme={isDark ? 'vs-dark' : 'light'}
                    onChange={handleEditorChange}
                    onMount={handleEditorMount}
                    loading={
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                            <CircularProgress size={32} />
                        </Box>
                    }
                    options={{
                        minimap: { enabled: false },
                        fontSize: 13,
                        fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
                        lineNumbers: 'on',
                        scrollBeyondLastLine: false,
                        wordWrap: 'on',
                        tabSize: 2,
                        automaticLayout: true,
                        renderWhitespace: 'selection',
                        bracketPairColorization: { enabled: true },
                        folding: true,
                        formatOnPaste: true,
                    }}
                />
            </Box>

            {/* Hidden file input for upload */}
            <input
                ref={fileInputRef}
                type="file"
                accept=".json,.yaml,.yml,.toml"
                style={{ display: 'none' }}
                onChange={handleFileSelected}
            />

            {/* Snackbar for feedback */}
            <Snackbar
                open={snackbar !== null}
                autoHideDuration={3000}
                onClose={() => setSnackbar(null)}
                anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
            >
                {snackbar ? (
                    <Alert
                        onClose={() => setSnackbar(null)}
                        severity={snackbar.severity}
                        variant="filled"
                        sx={{ width: '100%' }}
                    >
                        {snackbar.message}
                    </Alert>
                ) : undefined}
            </Snackbar>
        </Box>
    );
};
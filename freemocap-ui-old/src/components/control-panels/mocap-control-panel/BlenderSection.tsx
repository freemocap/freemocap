import React from 'react';
import {
    Alert,
    Box,
    Button,
    Checkbox,
    Divider,
    FormControlLabel,
    IconButton,
    InputAdornment,
    Stack,
    TextField,
    Tooltip,
    Typography,
} from '@mui/material';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import LaunchIcon from '@mui/icons-material/Launch';
import RefreshIcon from '@mui/icons-material/Refresh';
import ClearIcon from '@mui/icons-material/Clear';
import MovieFilterIcon from '@mui/icons-material/MovieFilter';
import {useBlender} from '@/hooks/useBlender';
import {useElectronIPC} from '@/services';

interface BlenderSectionProps {
    recordingFolderPath: string | null | undefined;
    disabled?: boolean;
    /** When provided, the "Open .blend in Blender" button is disabled unless true. */
    hasBlendFile?: boolean;
}

export const BlenderSection: React.FC<BlenderSectionProps> = ({
    recordingFolderPath,
    disabled = false,
    hasBlendFile,
}) => {
    const {api, isElectron} = useElectronIPC();
    const {
        effectiveBlenderExePath,
        isUsingManualBlenderPath,
        exportToBlenderEnabled,
        autoOpenBlendFile,
        isExporting,
        isDetecting,
        isOpening,
        lastBlendFilePath,
        error,
        redetectBlender,
        setBlenderExePath,
        clearBlenderExePath,
        setExportToBlenderEnabled,
        setAutoOpenBlendFile,
        triggerBlenderExport,
        triggerOpenInBlender,
        clearError,
    } = useBlender();

    const handleSelectBlenderExe = async (): Promise<void> => {
        if (!isElectron || !api) return;
        try {
            const result: string | null = await api.fileSystem.selectExecutableFile.mutate();
            if (result) {
                setBlenderExePath(result);
            }
        } catch (err) {
            console.error('Failed to select Blender executable:', err);
        }
    };

    const handleProcessWithBlender = (): void => {
        if (!recordingFolderPath) return;
        void triggerBlenderExport(recordingFolderPath);
    };

    const handleOpenInBlender = (): void => {
        if (!recordingFolderPath) return;
        void triggerOpenInBlender(recordingFolderPath);
    };

    const canExport =
        !!recordingFolderPath &&
        !!effectiveBlenderExePath &&
        !isExporting &&
        !disabled;

    const canOpen =
        !!recordingFolderPath &&
        !!effectiveBlenderExePath &&
        !isOpening &&
        !disabled &&
        (hasBlendFile === undefined || hasBlendFile);

    return (
        <Box sx={{mt: 1}}>
            <Divider sx={{mb: 2}}>
                <Stack direction="row" alignItems="center" spacing={0.5}>
                    <MovieFilterIcon fontSize="small"/>
                    <Typography variant="overline" sx={{lineHeight: 1}}>
                        Blender
                    </Typography>
                </Stack>
            </Divider>

            <Stack spacing={2}>
                {error && (
                    <Alert severity="error" onClose={clearError}>
                        {error}
                    </Alert>
                )}

                <TextField
                    label="Blender Executable"
                    value={effectiveBlenderExePath ?? ''}
                    onChange={(e) => setBlenderExePath(e.target.value || null)}
                    fullWidth
                    size="small"
                    placeholder={isDetecting ? 'Detecting…' : 'No Blender found — select manually'}
                    helperText={
                        isUsingManualBlenderPath
                            ? 'Using manually selected Blender'
                            : effectiveBlenderExePath
                                ? 'Auto-detected Blender'
                                : 'Click the folder icon to browse for blender.exe'
                    }
                    InputProps={{
                        endAdornment: (
                            <InputAdornment position="end">
                                {isUsingManualBlenderPath && (
                                    <Tooltip title="Clear manual path (revert to auto-detected)">
                                        <IconButton onClick={clearBlenderExePath} edge="end" size="small">
                                            <ClearIcon fontSize="small"/>
                                        </IconButton>
                                    </Tooltip>
                                )}
                                <Tooltip title="Re-detect Blender">
                                    <span>
                                        <IconButton
                                            onClick={redetectBlender}
                                            edge="end"
                                            size="small"
                                            disabled={isDetecting}
                                        >
                                            <RefreshIcon fontSize="small"/>
                                        </IconButton>
                                    </span>
                                </Tooltip>
                                <Tooltip title="Select Blender executable">
                                    <span>
                                        <IconButton
                                            onClick={handleSelectBlenderExe}
                                            edge="end"
                                            disabled={!isElectron}
                                        >
                                            <FolderOpenIcon/>
                                        </IconButton>
                                    </span>
                                </Tooltip>
                            </InputAdornment>
                        ),
                    }}
                />

                <Stack spacing={0.5}>
                    <FormControlLabel
                        control={
                            <Checkbox
                                size="small"
                                checked={exportToBlenderEnabled}
                                onChange={(e) => setExportToBlenderEnabled(e.target.checked)}
                            />
                        }
                        label="Export to Blender after mocap processing"
                    />
                    <FormControlLabel
                        control={
                            <Checkbox
                                size="small"
                                checked={autoOpenBlendFile}
                                onChange={(e) => setAutoOpenBlendFile(e.target.checked)}
                            />
                        }
                        label="Auto-open .blend file in Blender when done"
                    />
                </Stack>

                <Button
                    variant="outlined"
                    color="secondary"
                    startIcon={<MovieFilterIcon/>}
                    onClick={handleProcessWithBlender}
                    disabled={!canExport}
                    fullWidth
                >
                    {isExporting ? 'Exporting to Blender…' : 'Process Recording with Blender'}
                </Button>

                <Button
                    variant="outlined"
                    startIcon={<LaunchIcon/>}
                    onClick={handleOpenInBlender}
                    disabled={!canOpen}
                    fullWidth
                >
                    {isOpening ? 'Opening…' : 'Open .blend in Blender'}
                </Button>

                {lastBlendFilePath && (
                    <Typography variant="caption" color="text.secondary" sx={{fontFamily: 'monospace'}}>
                        Last export: {lastBlendFilePath}
                    </Typography>
                )}
            </Stack>
        </Box>
    );
};

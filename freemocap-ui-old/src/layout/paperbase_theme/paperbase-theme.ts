// freemocap-ui/src/layout/paperbase_theme/paperbase-theme.ts
import {createTheme, PaletteMode} from '@mui/material/styles';

// Define common theme settings
const getBaseTheme = (mode: PaletteMode) => ({
    typography: {
        h5: {
            fontWeight: 500,
            fontSize: 26,
            letterSpacing: 0.5,
        },
    },
    shape: {
        borderRadius: 8,
    },
    mixins: {
        toolbar: {
            minHeight: 48,
        },
    },
    components: {
        MuiTab: {
            defaultProps: {
                disableRipple: true,
            },
        },
    },
});

// Define the dark theme palette
const darkPalette = {
    mode: 'dark' as PaletteMode,
    primary: {
        light: '#00597f',
        main: '#002d46',
        dark: '#000b10',
    },
    background: {
        default: '#121212',
        paper: '#1e1e1e',
    },
    text: {
        primary: '#ffffff',
        secondary: '#b0b0b0',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
};

// Define the light theme palette
const lightPalette = {
    mode: 'light' as PaletteMode,
    primary: {
        light: '#4299e1',
        main: '#0067a3',
        dark: '#003e73',
    },
    background: {
        default: '#f5f5f5',
        paper: '#ffffff',
    },
    text: {
        primary: '#333333',
        secondary: '#555555',
    },
    divider: 'rgba(0, 0, 0, 0.12)',
};

// Create theme based on the palette mode
export const createAppTheme = (mode: PaletteMode) => {
    const baseTheme = getBaseTheme(mode);
    const palette = mode === 'dark' ? darkPalette : lightPalette;

    return createTheme({
        ...baseTheme,
        palette,
    });
};

// Export base themes for reference
export const paperbaseThemeLight = createAppTheme('light');
export const paperbaseThemeDark = createAppTheme('dark');

// Create the extended theme components that apply to both light/dark modes
export const createExtendedTheme = (mode: PaletteMode) => {
    const baseTheme = createAppTheme(mode);

    return {
        ...baseTheme,
        components: {
            ...baseTheme.components,
            MuiDrawer: {
                styleOverrides: {
                    paper: {
                        backgroundColor: mode === 'dark' ? '#081627' : '#f0f8ff',
                    },
                },
            },
            MuiButton: {
                styleOverrides: {
                    root: {
                        textTransform: 'none',
                    },
                    contained: {
                        boxShadow: 'none',
                        '&:active': {
                            boxShadow: 'none',
                        },
                    },
                },
            },
            MuiTabs: {
                styleOverrides: {
                    root: {
                        marginLeft: baseTheme.spacing(1),
                    },
                    indicator: {
                        height: 3,
                        borderTopLeftRadius: 3,
                        borderTopRightRadius: 3,
                        backgroundColor: mode === 'dark' ? baseTheme.palette.common.white : baseTheme.palette.primary.main,
                    },
                },
            },
            MuiTab: {
                styleOverrides: {
                    root: {
                        textTransform: 'none',
                        margin: '0 16px',
                        minWidth: 0,
                        padding: 0,
                        [baseTheme.breakpoints.up('md')]: {
                            padding: 0,
                            minWidth: 0,
                        },
                    },
                },
            },
            MuiIconButton: {
                styleOverrides: {
                    root: {
                        padding: baseTheme.spacing(1),
                    },
                },
            },
            MuiTooltip: {
                styleOverrides: {
                    tooltip: {
                        borderRadius: 4,
                    },
                },
            },
            MuiDivider: {
                styleOverrides: {
                    root: {
                        backgroundColor: mode === 'dark' ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)',
                    },
                },
            },
            MuiListItemButton: {
                styleOverrides: {
                    root: {
                        '&.Mui-selected': {
                            color: mode === 'dark' ? '#4fc3f7' : '#0067a3',
                        },
                    },
                },
            },
            MuiListItemText: {
                styleOverrides: {
                    primary: {
                        fontSize: 14,
                        fontWeight: baseTheme.typography.fontWeightMedium,
                    },
                },
            },
            MuiListItemIcon: {
                styleOverrides: {
                    root: {
                        color: 'inherit',
                        minWidth: 'auto',
                        marginRight: baseTheme.spacing(2),
                        '& svg': {
                            fontSize: 20,
                        },
                    },
                },
            },
            MuiAvatar: {
                styleOverrides: {
                    root: {
                        width: 32,
                        height: 32,
                    },
                },
            },
            MuiPanelResizeHandle: {
                styleOverrides: {
                    root: {
                        backgroundColor: mode === 'dark' ? baseTheme.palette.primary.light : baseTheme.palette.primary.main,
                        width: 4,
                        '&[data-panel-group-direction="horizontal"]': {
                            cursor: 'col-resize',
                        },
                        '&[data-panel-group-direction="vertical"]': {
                            height: 4,
                            cursor: 'row-resize',
                        },
                        '&:hover': {
                            backgroundColor: baseTheme.palette.secondary.main,
                        },
                        transition: 'background-color 0.2s ease',
                    },
                },
            },
            MuiTextField: {
                styleOverrides: {
                    root: {
                        '& .MuiOutlinedInput-root': {
                            color: mode === 'dark' ? 'white' : 'rgba(0, 0, 0, 0.87)',
                            '& fieldset': {
                                borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.5)' : 'rgba(0, 0, 0, 0.23)',
                            },
                            '&:hover fieldset': {
                                borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.87)',
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: mode === 'dark' ? 'white' : baseTheme.palette.primary.main,
                            },
                        },
                        '& .MuiInputLabel-root': {
                            color: mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.6)',
                        },
                        '& .MuiInputBase-input': {
                            color: mode === 'dark' ? 'white' : 'rgba(0, 0, 0, 0.87)',
                        },
                        '& .MuiIconButton-root': {
                            color: mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.54)',
                        },
                    },
                },
            },
            MuiTypography: {
                styleOverrides: {
                    root: {
                        color: mode === 'dark' ? 'white' : 'rgba(0, 0, 0, 0.87)',
                    },
                },
            },
        },
    };
};

// Re-export the default theme for backward compatibility
export const paperbaseTheme = paperbaseThemeDark;
export default createExtendedTheme('dark');

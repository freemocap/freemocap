// freemocap-ui/src/layout/paperbase_theme/paperbase-theme.ts
import {createTheme, PaletteMode} from '@mui/material/styles';

// Define common theme settings
const getBaseTheme = (mode: PaletteMode) => ({
    typography: {
        h5: {
            fontWeight: 500,
            fontSize: 22,
            letterSpacing: 0.5,
        },
        h6: {
            fontSize: 16,
            fontWeight: 500,
        },
        subtitle2: {
            fontSize: 13,
            fontWeight: 500,
        },
        body2: {
            fontSize: 13,
        },
        caption: {
            fontSize: 11,
        }
    },
    shape: {
        borderRadius: 6,
    },
    mixins: {
        toolbar: {
            minHeight: 40,
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

// Define the dark theme palette with better visibility
const darkPalette = {
    mode: 'dark' as PaletteMode,
    primary: {
        light: '#5e92f3',
        main: '#104172',
        dark: '#002a60',
        contrastText: '#ffffff',
    },
    secondary: {
        light: '#ff6090',
        main: '#f50057',
        dark: '#c51162',
        contrastText: '#ffffff',
    },
    background: {
        default: '#0a0e1a',
        paper: '#262f44',
    },
    text: {
        primary: '#ffffff',
        secondary: '#b3b9c6',
    },
    divider: 'rgba(255, 255, 255, 0.12)',
    action: {
        active: '#ffffff',
        hover: 'rgba(255, 255, 255, 0.08)',
        selected: 'rgba(255, 255, 255, 0.16)',
        disabled: 'rgba(255, 255, 255, 0.3)',
        disabledBackground: 'rgba(255, 255, 255, 0.12)',
    },
    success: {
        main: '#4caf50',
        light: '#80e27e',
        dark: '#087f23',
    },
    warning: {
        main: '#ff9800',
        light: '#ffcc80',
        dark: '#c66900',
    },
    error: {
        main: '#f44336',
        light: '#ff7961',
        dark: '#ba000d',
    },
    info: {
        main: '#29b6f6',
        light: '#73e8ff',
        dark: '#0086c3',
    },
    grey: {
        50: '#fafafa',
        100: '#f5f5f5',
        200: '#eeeeee',
        300: '#e0e0e0',
        400: '#bdbdbd',
        500: '#9e9e9e',
        600: '#757575',
        700: '#616161',
        800: '#424242',
        900: '#212121',
    },
};

// Define the light theme palette
const lightPalette = {
    mode: 'light' as PaletteMode,
    primary: {
        light: '#4791db',
        main: '#1976d2',
        dark: '#115293',
        contrastText: '#ffffff',
    },
    secondary: {
        light: '#ff5983',
        main: '#f50057',
        dark: '#ab003c',
        contrastText: '#ffffff',
    },
    background: {
        default: '#f5f7fa',
        paper: '#ffffff',
    },
    text: {
        primary: '#2c3e50',
        secondary: '#546e7a',
    },
    divider: 'rgba(0, 0, 0, 0.12)',
    action: {
        active: 'rgba(0, 0, 0, 0.54)',
        hover: 'rgba(0, 0, 0, 0.04)',
        selected: 'rgba(0, 0, 0, 0.08)',
        disabled: 'rgba(0, 0, 0, 0.26)',
        disabledBackground: 'rgba(0, 0, 0, 0.12)',
    },
    success: {
        main: '#4caf50',
        light: '#80e27e',
        dark: '#087f23',
    },
    warning: {
        main: '#ff9800',
        light: '#ffcc80',
        dark: '#c66900',
    },
    error: {
        main: '#f44336',
        light: '#ff7961',
        dark: '#ba000d',
    },
    info: {
        main: '#2196f3',
        light: '#64b5f6',
        dark: '#1565c0',
    },
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
                        backgroundColor: mode === 'dark' ? '#0f1419' : '#f8f9fa',
                    },
                },
            },
            MuiButton: {
                styleOverrides: {
                    root: {
                        textTransform: 'none',
                        fontSize: 12,
                        padding: '4px 12px',
                        minHeight: 28,
                    },
                    contained: {
                        boxShadow: 'none',
                        '&:active': {
                            boxShadow: 'none',
                        },
                    },
                },
            },
            MuiIconButton: {
                styleOverrides: {
                    root: {
                        padding: 6,
                    },
                    small: {
                        padding: 4,
                    },
                },
            },
            MuiCheckbox: {
                styleOverrides: {
                    root: {
                        color: mode === 'dark' ? baseTheme.palette.grey[400] : baseTheme.palette.grey[600],
                        '&.Mui-checked': {
                            color: baseTheme.palette.primary.main,
                        },
                        '&.Mui-disabled': {
                            color: mode === 'dark' ? baseTheme.palette.grey[700] : baseTheme.palette.grey[400],
                        },
                    },
                },
            },
            MuiRadio: {
                styleOverrides: {
                    root: {
                        color: mode === 'dark' ? baseTheme.palette.grey[400] : baseTheme.palette.grey[600],
                        '&.Mui-checked': {
                            color: baseTheme.palette.primary.main,
                        },
                    },
                },
            },
            MuiSwitch: {
                styleOverrides: {
                    root: {
                        padding: 8,
                    },
                    switchBase: {
                        padding: 9,
                        '&.Mui-checked': {
                            color: baseTheme.palette.primary.main,
                            '& + .MuiSwitch-track': {
                                backgroundColor: baseTheme.palette.primary.light,
                                opacity: 0.7,
                            },
                        },
                    },
                    track: {
                        backgroundColor: mode === 'dark' ? baseTheme.palette.grey[700] : baseTheme.palette.grey[400],
                    },
                },
            },
            MuiFormControlLabel: {
                styleOverrides: {
                    root: {
                        marginLeft: 0,
                        marginRight: 0,
                    },
                    label: {
                        fontSize: 12,
                    },
                },
            },
            MuiTreeItem: {
                styleOverrides: {
                    content: {
                        padding: '2px 8px',
                        margin: '2px 0',
                    },
                    label: {
                        fontSize: 13,
                        padding: '2px 0',
                    },
                },
            },
            MuiChip: {
                styleOverrides: {
                    root: {
                        height: 20,
                        fontSize: 11,
                    },
                    sizeSmall: {
                        height: 18,
                        fontSize: 10,
                    },
                },
            },
            MuiTextField: {
                styleOverrides: {
                    root: {
                        '& .MuiOutlinedInput-root': {
                            color: mode === 'dark' ? 'white' : 'rgba(0, 0, 0, 0.87)',
                            '& fieldset': {
                                borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.3)' : 'rgba(0, 0, 0, 0.23)',
                            },
                            '&:hover fieldset': {
                                borderColor: mode === 'dark' ? 'rgba(255, 255, 255, 0.5)' : 'rgba(0, 0, 0, 0.87)',
                            },
                            '&.Mui-focused fieldset': {
                                borderColor: baseTheme.palette.primary.main,
                            },
                        },
                        '& .MuiInputLabel-root': {
                            color: mode === 'dark' ? 'rgba(255, 255, 255, 0.7)' : 'rgba(0, 0, 0, 0.6)',
                            fontSize: 13,
                        },
                        '& .MuiInputBase-input': {
                            color: mode === 'dark' ? 'white' : 'rgba(0, 0, 0, 0.87)',
                            fontSize: 13,
                            padding: '8px 12px',
                        },
                        '& .MuiInputBase-inputSizeSmall': {
                            padding: '4px 8px',
                            fontSize: 12,
                        },
                    },
                },
            },
            MuiSelect: {
                styleOverrides: {
                    root: {
                        fontSize: 13,
                    },
                    select: {
                        padding: '8px 12px',
                    },
                },
            },
            MuiPaper: {
                styleOverrides: {
                    root: {
                        backgroundImage: 'none',
                    },
                },
            },
            MuiCard: {
                styleOverrides: {
                    root: {
                        backgroundImage: 'none',
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
            MuiDivider: {
                styleOverrides: {
                    root: {
                        backgroundColor: mode === 'dark' ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.08)',
                    },
                },
            },
            MuiTooltip: {
                styleOverrides: {
                    tooltip: {
                        borderRadius: 4,
                        fontSize: 11,
                    },
                },
            },
            MuiListItemButton: {
                styleOverrides: {
                    root: {
                        padding: '4px 8px',
                        '&.Mui-selected': {
                            backgroundColor: mode === 'dark'
                                ? 'rgba(25, 118, 210, 0.16)'
                                : 'rgba(25, 118, 210, 0.08)',
                            color: baseTheme.palette.primary.main,
                        },
                    },
                },
            },
            MuiListItemText: {
                styleOverrides: {
                    primary: {
                        fontSize: 13,
                        fontWeight: baseTheme.typography.fontWeightMedium,
                    },
                },
            },
            MuiListItemIcon: {
                styleOverrides: {
                    root: {
                        color: 'inherit',
                        minWidth: 'auto',
                        marginRight: baseTheme.spacing(1),
                        '& svg': {
                            fontSize: 18,
                        },
                    },
                },
            },
        },
    };
};

// Re-export the default theme for backward compatibility
export const paperbaseTheme = paperbaseThemeDark;
export default createExtendedTheme('dark');

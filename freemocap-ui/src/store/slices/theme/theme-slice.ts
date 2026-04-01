import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { ThemeMode } from './theme-types';

const getInitialTheme = (): ThemeMode => {
    if (typeof window !== 'undefined') {
        const saved = localStorage.getItem('themeMode');
        if (saved === 'light' || saved === 'dark') {
            return saved;
        }
        // Check system preference
        if (window.matchMedia?.('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
    }
    return 'dark';
};

interface ThemeState {
    mode: ThemeMode;
    systemPreference: ThemeMode | null;
}

const initialState: ThemeState = {
    mode: getInitialTheme(),
    systemPreference: null,
};

export const themeSlice = createSlice({
    name: 'theme',
    initialState,
    reducers: {
        themeModeSet: (state, action: PayloadAction<ThemeMode>) => {
            state.mode = action.payload;
            localStorage.setItem('themeMode', action.payload);
        },
        themeModeToggled: (state) => {
            state.mode = state.mode === 'dark' ? 'light' : 'dark';
            localStorage.setItem('themeMode', state.mode);
        },
        systemPreferenceUpdated: (state, action: PayloadAction<ThemeMode>) => {
            state.systemPreference = action.payload;
        },
    },
});

export const {
    themeModeSet,
    themeModeToggled,
    systemPreferenceUpdated,
} = themeSlice.actions;

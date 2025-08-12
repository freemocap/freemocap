// skellycam-ui/src/store/slices/themeSlice.ts
import {createSlice, PayloadAction} from "@reduxjs/toolkit";

export type ThemeMode = 'light' | 'dark';

interface ThemeState {
  mode: ThemeMode;
}

// Get initial theme from localStorage or default to 'dark'
const getInitialTheme = (): ThemeMode => {
  const savedTheme = localStorage.getItem('themeMode');
  // Check if in browser environment (not SSR)
  if (typeof window !== 'undefined') {
    // Check for saved preference first
    if (savedTheme && (savedTheme === 'light' || savedTheme === 'dark')) {
      return savedTheme;
    }
    // Otherwise check system preference
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark';
    }
  }
  // Default to dark theme
  return 'dark';
};

const initialState: ThemeState = {
  mode: getInitialTheme(),
};

export const themeSlice = createSlice({
  name: "theme",
  initialState,
  reducers: {
    setThemeMode: (state, action: PayloadAction<ThemeMode>) => {
      state.mode = action.payload;
      // Save to localStorage for persistence
      localStorage.setItem('themeMode', action.payload);
    },
    toggleThemeMode: (state) => {
      state.mode = state.mode === 'dark' ? 'light' : 'dark';
      // Save to localStorage for persistence
      localStorage.setItem('themeMode', state.mode);
    },
  },
});

export const { setThemeMode, toggleThemeMode } = themeSlice.actions;
export default themeSlice.reducer;

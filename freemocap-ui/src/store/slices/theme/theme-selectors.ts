import {RootState} from '../../types';

export const selectThemeMode = (state: RootState) => state.theme.mode;
export const selectSystemThemePreference = (state: RootState) =>
    state.theme.systemPreference;

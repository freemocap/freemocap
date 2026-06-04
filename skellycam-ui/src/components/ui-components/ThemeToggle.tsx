import React from 'react';
import { useAppDispatch, useAppSelector } from '@/store';
import { themeModeToggled } from '@/store/slices/theme';
import { useTranslation } from 'react-i18next';

export const ThemeToggle: React.FC = () => {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const themeMode = useAppSelector(state => state.theme.mode);
    const isDarkMode = themeMode === 'dark';

    return (
        <button
            className="button icon-button"
            onClick={() => dispatch(themeModeToggled())}
            title={isDarkMode ? t('switchToLight') : t('switchToDark')}
            aria-label={t('toggleTheme')}
        >
            <span className="text sm">{isDarkMode ? '☀' : '☾'}</span>
        </button>
    );
};

export default ThemeToggle;

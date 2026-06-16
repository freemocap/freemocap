import React from 'react';
import {IconButton, Tooltip, useTheme} from '@mui/material';
import Brightness4Icon from '@mui/icons-material/Brightness4'; // Dark mode icon
import Brightness7Icon from '@mui/icons-material/Brightness7'; // Light mode icon
import {useAppDispatch, useAppSelector} from '@/store';
import {themeModeToggled} from '@/store/slices/theme';
import {useTranslation} from 'react-i18next';

export const ThemeToggle: React.FC = () => {
    const dispatch = useAppDispatch();
    const theme = useTheme();
    const { t } = useTranslation();
    const themeMode = useAppSelector(state => state.theme.mode);
    const isDarkMode = themeMode === 'dark';

    return (
        <Tooltip title={isDarkMode ? t("switchToLight") : t("switchToDark")}>
            <IconButton
                onClick={() => dispatch(themeModeToggled())}
                color="inherit"
                aria-label={t("toggleTheme")}
                edge="end"
                sx={{
                    '&:hover': {
                        backgroundColor: theme.palette.action.hover,
                    },
                }}
            >
                {isDarkMode ? <Brightness7Icon /> : <Brightness4Icon />}
            </IconButton>
        </Tooltip>
    );
};

export default ThemeToggle;

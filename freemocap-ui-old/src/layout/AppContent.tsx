import * as React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { HashRouter } from 'react-router-dom';
import { CssBaseline } from '@mui/material';
import { BasePanelLayout } from '@/layout/BasePanelLayout';
import { createExtendedTheme } from '@/layout/paperbase-theme';
import { useAppSelector } from '@/store';
import { BaseContentRouter } from '@/layout/BaseContentRouter';
import { FirstLaunchRedirect } from '@/components/setup-wizard/FirstLaunchRedirect';
import { MenuNavigationListener } from '@/components/MenuNavigationListener';

export const AppContent = function () {
    const themeMode = useAppSelector(state => state.theme.mode);

    const theme = React.useMemo(() =>
            createExtendedTheme(themeMode),
        [themeMode],
    );

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <HashRouter>
                <FirstLaunchRedirect />
                <MenuNavigationListener />
                <BasePanelLayout>
                    <BaseContentRouter />
                </BasePanelLayout>
            </HashRouter>
        </ThemeProvider>
    );
};

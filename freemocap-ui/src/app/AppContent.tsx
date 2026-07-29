import * as React from 'react';
import { createTheme, ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from "@mui/material";
import { HashRouter, Route, Routes } from 'react-router-dom';
import { BasePanelLayout } from "@/layout/BasePanelLayout";
import { useAppDispatch, useAppSelector } from "@/store";
import { BaseContentRouter } from "@/layout/content/BaseContentRouter";
import { UpdateBanner } from "@/components/ui-components/UpdateBanner";
import PipelineProgressSnackbar from "@/components/pipeline-progress/PipelineProgressSnackbar";
import { AutoUpdateProvider } from "@/hooks/AutoUpdateContext";
import { PlaybackProvider } from "@/components/playback/PlaybackContext";
import { useTranslation } from "react-i18next";
import { getLocaleDirection } from "@/i18n";
import { fetchAllRecordings } from "@/store/slices/recording-status/recording-status-thunks";
import { WelcomeModal } from "@/components/ui-components/WelcomeModal";
import { SettingsModal } from "@/components/ui-components/SettingsModal";
import { TutorialProvider, TourController } from "@/components/tutorial";
import PipelineMetricsWindowPage from "@/components/pipeline-metrics/PipelineMetricsWindowPage";

type AppContentProps = {
    metricsOnly?: boolean;
};

export const AppContent = function ({ metricsOnly = false }: AppContentProps) {
    const { i18n } = useTranslation();
    const dispatch = useAppDispatch();
    const direction = getLocaleDirection(i18n.language);
    const [welcomeOpen, setWelcomeOpen] = React.useState(true);
    const [settingsOpen, setSettingsOpen] = React.useState(false);

    // The native menu's "Settings…" fires this event (see useMenuActions).
    React.useEffect(() => {
        const openSettings = () => setSettingsOpen(true);
        window.addEventListener('open-settings', openSettings);
        return () => window.removeEventListener('open-settings', openSettings);
    }, []);

    React.useEffect(() => {
        document.documentElement.dir = direction;
        document.documentElement.lang = i18n.language;
    }, [direction, i18n.language]);

    React.useEffect(() => {
        dispatch(fetchAllRecordings());
    }, [dispatch]);

    if (metricsOnly) {
        const themeMode = useAppSelector(state => state.theme.mode);
        const theme = React.useMemo(
            () => createTheme({ palette: { mode: themeMode }, direction }),
            [themeMode, direction],
        );
        return (
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <PipelineMetricsWindowPage />
            </ThemeProvider>
        );
    }

    return (
        <HashRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <AutoUpdateProvider>
                <TutorialProvider>
                    <PlaybackProvider>
                        <BasePanelLayout onOpenWelcome={() => setWelcomeOpen(true)}>
                            <BaseContentRouter />
                        </BasePanelLayout>
                        <WelcomeModal open={welcomeOpen} onClose={() => setWelcomeOpen(false)} />
                        <SettingsModal open={settingsOpen} onClose={() => setSettingsOpen(false)} />
                        <TourController />
                    </PlaybackProvider>
                </TutorialProvider>
                <UpdateBanner />
                <PipelineProgressSnackbar />
            </AutoUpdateProvider>
        </HashRouter>
    );
}

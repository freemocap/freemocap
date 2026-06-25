import * as React from 'react';
import { ThemeProvider } from '@mui/material/styles';
import { HashRouter, Route, Routes } from 'react-router-dom';
import { CssBaseline } from "@mui/material";
import { BasePanelLayout } from "@/layout/BasePanelLayout";
import { createExtendedTheme } from "@/layout/paperbase-theme";
import { useAppDispatch, useAppSelector } from "@/store";
import { BaseContentRouter } from "@/layout/content/BaseContentRouter";
import { UpdateBanner } from "@/components/ui-components/UpdateBanner";
import PipelineProgressSnackbar from "@/components/pipeline-progress/PipelineProgressSnackbar";
import { AutoUpdateProvider } from "@/hooks/AutoUpdateContext";
import { PlaybackProvider } from "@/components/playback/PlaybackContext";
import { useTranslation } from "react-i18next";
import { getLocaleDirection } from "@/i18n";
import { fetchAllRecordings } from "@/store/slices/recording-status/recording-status-thunks";
import PipelineMetricsWindowPage from "@/components/pipeline-metrics/PipelineMetricsWindowPage";

type AppContentProps = {
    metricsOnly?: boolean;
};

export const AppContent = function ({ metricsOnly = false}: AppContentProps) {
    const { i18n } = useTranslation();
    const dispatch = useAppDispatch();
    const themeMode = useAppSelector(state => state.theme.mode);
    const direction = getLocaleDirection(i18n.language);

    React.useEffect(() => {
        document.documentElement.dir = direction;
        document.documentElement.lang = i18n.language;
    }, [direction, i18n.language]);

    React.useEffect(() => {
        if (metricsOnly) return;
        dispatch(fetchAllRecordings());
    }, [dispatch, metricsOnly]);

    const theme = React.useMemo(() => {
        const base = createExtendedTheme(themeMode);
        return { ...base, direction };
    }, [themeMode, direction]);

    if (metricsOnly) {
        return (
            <ThemeProvider theme={theme}>
                <CssBaseline />
                <HashRouter>
                    <Routes>
                        <Route path="/pipeline-metrics" element={<PipelineMetricsWindowPage />} />
                        <Route path="*" element={<PipelineMetricsWindowPage />} />
                    </Routes>
                </HashRouter>
            </ThemeProvider>
        );
    }

    return (
        <ThemeProvider theme={theme}>
            <CssBaseline />
            <HashRouter>
                <AutoUpdateProvider>
                    <PlaybackProvider>
                        <BasePanelLayout>
                            <BaseContentRouter />
                        </BasePanelLayout>
                    </PlaybackProvider>
                    <UpdateBanner />
                    <PipelineProgressSnackbar />
                </AutoUpdateProvider>
            </HashRouter>
        </ThemeProvider>
    );
};

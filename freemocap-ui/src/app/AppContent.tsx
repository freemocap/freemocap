import * as React from 'react';
import { HashRouter } from 'react-router-dom';
import { BasePanelLayout } from "@/layout/BasePanelLayout";
import { useAppDispatch } from "@/store";
import { BaseContentRouter } from "@/layout/content/BaseContentRouter";
import { UpdateBanner } from "@/components/ui-components/UpdateBanner";
import PipelineProgressSnackbar from "@/components/pipeline-progress/PipelineProgressSnackbar";
import { AutoUpdateProvider } from "@/hooks/AutoUpdateContext";
import { PlaybackProvider } from "@/components/playback/PlaybackContext";
import { useTranslation } from "react-i18next";
import { getLocaleDirection } from "@/i18n";
import { fetchAllRecordings } from "@/store/slices/recording-status/recording-status-thunks";
import { WelcomeModal } from "@/components/ui-components/WelcomeModal";

export const AppContent = function () {
    const { i18n } = useTranslation();
    const dispatch = useAppDispatch();
    const direction = getLocaleDirection(i18n.language);
    const [welcomeOpen, setWelcomeOpen] = React.useState(true);

    React.useEffect(() => {
        document.documentElement.dir = direction;
        document.documentElement.lang = i18n.language;
    }, [direction, i18n.language]);

    React.useEffect(() => {
        dispatch(fetchAllRecordings());
    }, [dispatch]);

    return (
        <HashRouter>
            <AutoUpdateProvider>
                <PlaybackProvider>
                    <BasePanelLayout>
                        <BaseContentRouter />
                    </BasePanelLayout>
                    <WelcomeModal open={welcomeOpen} onClose={() => setWelcomeOpen(false)} />
                </PlaybackProvider>
                <UpdateBanner />
                <PipelineProgressSnackbar />
            </AutoUpdateProvider>
        </HashRouter>
    );
}

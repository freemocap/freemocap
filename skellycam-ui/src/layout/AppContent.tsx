import * as React from 'react';
import {HashRouter} from 'react-router-dom';
import {BasePanelLayout} from "@/layout/BasePanelLayout";
import {MainTabPanel} from "@/layout/MainTabPanel";
import {UpdateBanner} from "@/components/ui-components/UpdateBanner";
import {AutoUpdateProvider} from "@/hooks/AutoUpdateContext";
import {useTranslation} from "react-i18next";
import {getLocaleDirection} from "@/i18n";
import {WelcomeModal} from "@/components/ui-components/WelcomeModal";
import {RecordingGuardProvider} from "@/components/RecordingGuardProvider";
import {PlaybackContextProvider} from "@/contexts/PlaybackContext";

export const AppContent = function () {
    const {i18n} = useTranslation();
    const direction = getLocaleDirection(i18n.language);
    const [welcomeOpen, setWelcomeOpen] = React.useState(true);

    React.useEffect(() => {
        document.documentElement.dir = direction;
        document.documentElement.lang = i18n.language;
    }, [direction, i18n.language]);

    return (
        <HashRouter>
            <AutoUpdateProvider>
                <RecordingGuardProvider>
                    <PlaybackContextProvider>
                    <BasePanelLayout welcomeOpen={welcomeOpen} onOpenWelcome={() => setWelcomeOpen(true)}>
                        <MainTabPanel/>
                    </BasePanelLayout>
                    </PlaybackContextProvider>
                    <UpdateBanner/>
                    <WelcomeModal open={welcomeOpen} onClose={() => setWelcomeOpen(false)} />
                </RecordingGuardProvider>
            </AutoUpdateProvider>
        </HashRouter>
    );
}

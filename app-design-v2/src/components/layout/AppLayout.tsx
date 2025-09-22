import { useState, type FC, type ReactElement } from "react";
import "../../App.css";
import SplashModal from "../features/SplashModal/SplashModal.tsx";

// Import sub-components with their types
import { Header } from "./Header.tsx";
import { MainContentPanel } from "./MainContentPanel.tsx";
import { SidePanel, type SidePanelSettings } from "./SidePanel.tsx";
import { BottomPanel, type InfoMode } from "./BottomPanel.tsx";

export interface AppLayoutProps {
    initialShowSplash?: boolean;
    onGlobalStateChange?: (componentName: string, state: unknown) => void;
}

const AppLayout: FC<AppLayoutProps> = ({
                                           initialShowSplash = true,
                                           onGlobalStateChange,
                                       }): ReactElement => {
    const [showSplash, setShowSplash] = useState<boolean>(initialShowSplash);

    // Event handlers for cross-component communication
    const handleModeChange = (mode: string): void => {
        console.log("Mode changed to:", mode);
        if (onGlobalStateChange) {
            onGlobalStateChange("MainContentPanel", { mode });
        }
    };

    const handleStreamStateChange = (state: string): void => {
        console.log("Stream state changed to:", state);
        if (onGlobalStateChange) {
            onGlobalStateChange("MainContentPanel", { streamState: state });
        }
    };

    const handleSettingsChange = (settings: SidePanelSettings): void => {
        console.log("Settings updated:", settings);
        if (onGlobalStateChange) {
            onGlobalStateChange("SidePanel", settings);
        }
    };

    const handleInfoModeChange = (mode: InfoMode): void => {
        console.log("Info mode changed to:", mode);
        if (onGlobalStateChange) {
            onGlobalStateChange("BottomPanel", { infoMode: mode });
        }
    };

    const handleSupportClick = (): void => {
        console.log("Support freemocap clicked");
        // TODO: Navigate to donation page
        window.open("https://freemocap.org/donate", "_blank");
    };

    const handleHelpItemClick = (item: string): void => {
        const helpUrls: Record<string, string> = {
            "FreeMocap Guide": "https://freemocap.org/guide",
            "Ask Question on Discord": "https://discord.gg/freemocap",
            "Download Sample Videos": "https://freemocap.org/samples"
        };

        const url: string | undefined = helpUrls[item];
        if (url) {
            window.open(url, "_blank");
        }
    };

    const handleCalibrateClick = (): void => {
        console.log("Starting calibration process...");
        // TODO: Implement calibration logic
    };

    const handleRecordClick = (): void => {
        console.log("Starting recording...");
        // TODO: Implement recording logic
    };

    const handleCloseSplash = (): void => {
        setShowSplash(false);
    };

    return (
        <div className="app-content bg-middark flex flex-col p-1 gap-1 h-full overflow-hidden">
            {/* Splash Modal */}
            {showSplash && <SplashModal onClose={handleCloseSplash} />}

            {/* Header Component */}
            <Header
                onSupportClick={handleSupportClick}
                onHelpItemClick={handleHelpItemClick}
            />

            {/* Main Container */}
            <div className="main-container gap-1 overflow-hidden flex flex-row flex-1">
                {/* Main Content Panel */}
                <MainContentPanel
                    onModeChange={handleModeChange}
                    onStreamStateChange={handleStreamStateChange}
                />

                {/* Side Panel */}
                <SidePanel
                    onSettingsChange={handleSettingsChange}
                    onCalibrateClick={handleCalibrateClick}
                    onRecordClick={handleRecordClick}
                />
            </div>

            {/* Bottom Panel */}
            <BottomPanel
                onInfoModeChange={handleInfoModeChange}
            />
        </div>
    );
};

export default AppLayout;

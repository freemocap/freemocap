import {type FC, type ReactElement, useState} from "react";
import "../../App.css";
import SplashModal from "../features/SplashModal/SplashModal.tsx";

// Import sub-components with their types
import {Header} from "./Header.tsx";
import {MainContentPanel} from "./MainContentPanel.tsx";
import {SidePanel, type SidePanelSettings} from "./SidePanel.tsx";
import {BottomPanel, type InfoMode} from "./BottomPanel.tsx";

export interface AppLayoutProps {
    initialShowSplash?: boolean;
    onGlobalStateChange?: (componentName: string, state: unknown) => void;
}

const AppLayout: FC<AppLayoutProps> = ({
                                           initialShowSplash = true,
                                           onGlobalStateChange,
                                       }): ReactElement => {
    const [showSplash, setShowSplash] = useState<boolean>(initialShowSplash);


    const handleCloseSplash = (): void => {
        setShowSplash(false);
    };

    return (
        <div className="app-content bg-middark flex flex-col p-1 gap-1 h-full overflow-hidden">
            {/* Splash Modal */}
            {showSplash && <SplashModal onClose={handleCloseSplash}/>}

            {/* Header Component */}
            <Header/>

            {/* Main Container */}
            <div className="main-container gap-1 overflow-hidden flex flex-row flex-1">
                {/* Main Content Panel */}
                <MainContentPanel/>

                {/* Side Panel */}
                <SidePanel/>
            </div>

            {/* Bottom Panel */}
            <BottomPanel/>
        </div>
    );
};

export default AppLayout;

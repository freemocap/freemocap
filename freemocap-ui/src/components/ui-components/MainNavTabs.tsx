import React, { useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";

// Active-recording responsibilities were folded into the Playback tab, so only
// these two top-level modes remain.
const NAV_TABS = [
    { path: '/streaming', label: 'Streaming', onboarding: 'nav:streaming' },
    { path: '/playback', label: 'Playback', onboarding: 'nav:playback' },
] as const;

export const MainNavTabs = () => {
    const location = useLocation();
    const navigate = useNavigate();

    const activeIdx = useMemo(() => {
        const idx = NAV_TABS.findIndex(t => location.pathname === t.path);
        return idx >= 0 ? idx : 0;
    }, [location.pathname]);

    const handleClick = useCallback((path: string) => {
        navigate(path);
    }, [navigate]);

    return (
        <div className="main-tab-bar main-tab-bar-container pos-abs top-0 left-0 main-segmented-control-container">
            <div data-onboarding="nav:tabs" className="segmented-control-container bg-middark br-2 gap-1 p-1 z-1 flex flex-row">
                {NAV_TABS.map((tab, idx) => {
                    const isActive = idx === activeIdx;
                    return (
                        <div
                            key={tab.path}
                            data-onboarding={tab.onboarding}
                            className={`segmented-control-button justify-center button pl-2 pr-2 gap-1 br-1 flex-inline items-center cursor-pointer${isActive ? ' bg-dark' : ''}`}
                            onClick={() => handleClick(tab.path)}
                            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleClick(tab.path); } }}
                        >
                            <p className={`text md text-center p-1 ${isActive ? ' text-white' : ' text-gray'}`}>{tab.label}</p>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

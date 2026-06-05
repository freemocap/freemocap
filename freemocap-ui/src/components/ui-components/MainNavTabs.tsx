import React, { useCallback, useMemo } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useAppDispatch, useAppSelector } from "@/store";
import {
    activeRecordingCleared,
    selectActiveRecordingFullPath,
    selectActiveRecordingName,
} from "@/store/slices/active-recording/active-recording-slice";
import { useElectronIPC } from "@/services";

const NAV_TABS = [
    { path: '/streaming', label: 'Streaming' },
    { path: '/playback', label: 'Playback' },
    { path: '/browse', label: 'Recordings' },
    { path: '/active-recording', label: 'Active Recording' },
] as const;

const ActiveRecordingLabel: React.FC = () => {
    const dispatch = useAppDispatch();
    const recordingName = useAppSelector(selectActiveRecordingName);
    const fullPath = useAppSelector(selectActiveRecordingFullPath);
    const { api } = useElectronIPC();

    const handleOpenFolder = async (e: React.MouseEvent) => {
        e.stopPropagation();
        if (!fullPath) return;
        try {
            await api?.fileSystem.openFolder.mutate({ path: fullPath });
        } catch (err) {
            console.error('Failed to open recording folder:', err);
        }
    };

    const handleClearRecording = (e: React.MouseEvent) => {
        e.stopPropagation();
        dispatch(activeRecordingCleared());
    };

    return (
        <span className="flex flex-row items-center gap-1">
            <span>Active Recording</span>
            {recordingName ? (
                <span
                    className="tag text sm"
                    style={{ fontFamily: 'monospace', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                    title={fullPath ?? recordingName}
                    onClick={handleOpenFolder}
                >
                    {recordingName}
                    <button
                        className="button icon-button"
                        onClick={handleClearRecording}
                        style={{ marginLeft: 4, lineHeight: 1 }}
                        title="Clear active recording"
                    >
                        <span className="icon close-icon icon-size-12" />
                    </button>
                </span>
            ) : (
                <span className="text sm text-gray" style={{ fontStyle: 'italic' }}>(none)</span>
            )}
        </span>
    );
};

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
        <div className="main-tab-bar">
            <div className="segmented-control-container br-1-1 gap-1 p-1 bg-middark flex flex-row">
                {NAV_TABS.map((tab, idx) => {
                    const isActive = idx === activeIdx;
                    return (
                        <button
                            key={tab.path}
                            className={`segmented-control-button justify-center button pl-2 pr-2 gap-1 br-1 flex-inline items-center${isActive ? ' bg-dark' : ''}`}
                            onClick={() => handleClick(tab.path)}
                        >
                            {tab.path === '/active-recording'
                                ? <ActiveRecordingLabel />
                                : <p className={`text md text-center p-1${isActive ? ' text-white' : ' text-gray'}`}>{tab.label}</p>
                            }
                        </button>
                    );
                })}
            </div>
        </div>
    );
};
